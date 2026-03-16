"""
Celery Task 설계 원칙:
- 각 task는 단일 책임 (룩업 sync / 게임 sync)
- 재시도: autoretry_for + exponential backoff
- 멱등성: upsert 구조이므로 재실행 안전
- task는 서비스 레이어 호출만 담당; 비즈니스 로직은 서비스에 위임

Redis Lock 흐름:
    RawgSyncView.post() → cache.get(_LOCK_KEY) 체크 → 있으면 409 반환
    sync_all_games / incremental_sync 시작 시 → cache.set(_LOCK_KEY)
    완료/실패 시 finally → cache.delete(_LOCK_KEY)

Celery 태스크 테스트 방법:
    1. 단위 테스트 - 브로커 없이 동기 실행
       task.apply() / task.apply(kwargs={...})

    2. settings/test.py에 추가
       CELERY_TASK_ALWAYS_EAGER = True
       CELERY_TASK_EAGER_PROPAGATES = True

    3. 태스크 등록 확인
       celery -A config inspect registered
       → apps.games.tasks.incremental_sync 등이 목록에 있어야 함
"""

from __future__ import annotations

import logging
from typing import Any

from celery import chain, shared_task

from apps.games.rawg.exceptions import RawgRateLimitError, RawgServerError
from apps.games.services.rawg_sync import RawgSyncService

logger = logging.getLogger(__name__)

_LOCK_KEY = "rawg_sync_running"
_LOCK_TIMEOUT = 60 * 60 * 8  # 8시간


# 룩업 테이블 -------------------------------------------------
@shared_task(
    bind=True,
    name="apps.games.tasks.sync_lookup_tables",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(RawgServerError,),
    retry_backoff=True,
    retry_backoff_max=300,
    acks_late=True,
    time_limit=600,
    soft_time_limit=540,
)
def sync_lookup_tables(self: Any) -> dict[str, Any]:
    """
    장르·플랫폼·태그·스토어 전체 동기화
    게임 sync 전에 반드시 먼저 실행해야 FK 참조 가능.
    """
    service = RawgSyncService()
    try:
        result = {
            "genres": service.sync_genres(),
            "platforms": service.sync_platforms(),
            "tags": service.sync_tags(),
            "stores": service.sync_stores(),
        }
        logger.info("lookup_tables sync 완료: %s", result)
        return result
    except RawgRateLimitError as exc:
        logger.warning("Rate limit 발생, 5분 후 재시도: %s", exc)
        raise self.retry(exc=exc, countdown=300) from exc


# 게임 전체 동기화 -----------------------------------------------
@shared_task(
    bind=True,
    name="apps.games.tasks.sync_all_games",
    max_retries=3,
    default_retry_delay=120,
    autoretry_for=(RawgServerError,),
    retry_backoff=True,
    retry_backoff_max=600,
    acks_late=True,
    soft_time_limit=21_600,  # 6시간
    time_limit=25_200,  # 7시간
)
def sync_all_games(
    self: Any,
    ordering: str = "-added",
    max_pages: int | None = None,
    fetch_detail: bool = True,
) -> dict[str, Any]:
    """
    RAWG /games 전체 동기화

    Args:
        ordering: RAWG 정렬 기준 (기본 '-added': 추가 순)
        max_pages: None이면 전체, 숫자면 해당 페이지 수만큼
        fetch_detail: True면 각 게임마다 /games/{id} 추가 호출
    """
    from django.core.cache import cache

    cache.set(_LOCK_KEY, True, timeout=_LOCK_TIMEOUT)
    try:
        self.update_state(state="PROGRESS", meta={"status": "started"})
        service = RawgSyncService()
        result = service.sync_games(
            ordering=ordering,
            max_pages=max_pages,
            fetch_detail=fetch_detail,
        )
        logger.info("게임 sync 완료: %s", result)
        return result

    except RawgRateLimitError as exc:
        logger.warning("게임 sync rate limit, 10분 후 재시도: %s", exc)
        raise self.retry(exc=exc, countdown=600) from exc

    finally:
        cache.delete(_LOCK_KEY)


# 주기적 증분 동기화 (Celery Beat) ---------------------------------------
@shared_task(
    name="apps.games.tasks.incremental_sync",
    max_retries=2,
    acks_late=True,
    time_limit=3600 * 2,
    soft_time_limit=3600,
)
def incremental_sync() -> None:
    """
    Celery Beat에 등록하여 정기 실행 (매일 새벽 3시)
    최근 변경된 게임 위주로 앞 N 페이지만 sync합니다.

    - Redis Lock으로 중복 실행 방지 (체인 실행 후 lock 자동 해제)
    - lookup → 게임 sync 순서대로 체인 실행
    """
    from django.core.cache import cache

    if cache.get(_LOCK_KEY):
        logger.info("incremental_sync: 이미 실행 중, 중복 방지")
        return

    # Lock 설정
    cache.set(_LOCK_KEY, True, timeout=_LOCK_TIMEOUT)
    logger.info("incremental_sync: lock 설정 완료")

    try:
        # si() → immutable signature를 생성. 이전 task 결과를 전달하지 않고, 명시한 인자만 전달됨.
        # 체인 내부에서 인자는 kwargs로 전달
        task_chain = chain(
            sync_lookup_tables.si(),  # lookup 테이블 먼저
            sync_all_games.si(ordering="-updated", max_pages=50, fetch_detail=True),
        )

        # 체인 실행
        task_chain.apply_async()
        logger.info("incremental_sync: task chain 실행 완료")

    finally:
        # task_chain 자체가 비동기라서 chain 끝나기 전에 unlock 하면 안 됨
        # unlock은 sync_all_games task 끝에서 처리
        # 따라서 여기서는 lock 해제 안 함
        pass
