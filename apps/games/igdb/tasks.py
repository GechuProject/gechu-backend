"""
IGDB Celery Tasks

RAWG tasks.py와 동일한 구조 유지:
- sync_lookup_tables: 장르·플랫폼·키워드 동기화
- sync_all_games: 게임 전체 동기화
- incremental_sync: 주기적 증분 동기화 (Celery Beat)

Redis Lock:
    _LOCK_KEY = "igdb_sync_running"
    sync_all_games 시작 시 set, 완료/실패 시 finally에서 delete
"""

from __future__ import annotations

import logging
from typing import Any

from celery import chain, shared_task

from .exceptions import IgdbRateLimitError, IgdbServerError
from .service import IgdbSyncService

logger = logging.getLogger(__name__)

_LOCK_KEY = "igdb_sync_running"
_LOCK_TIMEOUT = 60 * 60 * 8  # 8시간


@shared_task(
    bind=True,
    name="apps.games.igdb.tasks.sync_lookup_tables",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(IgdbServerError,),
    retry_backoff=True,
    retry_backoff_max=300,
    acks_late=True,
    time_limit=600,
    soft_time_limit=540,
)
def sync_lookup_tables(self: Any) -> dict[str, Any]:
    """장르·플랫폼·키워드(태그) 전체 동기화"""
    service = IgdbSyncService()
    try:
        result = {
            "genres": service.sync_genres(),
            "platforms": service.sync_platforms(),
            "tags": service.sync_tags(),
        }
        logger.info("IGDB lookup_tables sync 완료: %s", result)
        return result
    except IgdbRateLimitError as exc:
        logger.warning("Rate limit 발생, 5분 후 재시도: %s", exc)
        raise self.retry(exc=exc, countdown=300) from exc


@shared_task(
    bind=True,
    name="apps.games.igdb.tasks.sync_all_games",
    max_retries=3,
    default_retry_delay=120,
    autoretry_for=(IgdbServerError,),
    retry_backoff=True,
    retry_backoff_max=600,
    acks_late=True,
    soft_time_limit=21_600,
    time_limit=25_200,
)
def sync_all_games(
    self: Any,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """IGDB /games 전체 동기화"""
    from django.core.cache import cache

    cache.set(_LOCK_KEY, True, timeout=_LOCK_TIMEOUT)
    try:
        self.update_state(state="PROGRESS", meta={"status": "started"})
        service = IgdbSyncService()
        result = service.sync_games(max_pages=max_pages)
        logger.info("IGDB 게임 sync 완료: %s", result)
        return result
    except IgdbRateLimitError as exc:
        logger.warning("IGDB 게임 sync rate limit, 10분 후 재시도: %s", exc)
        raise self.retry(exc=exc, countdown=600) from exc
    finally:
        cache.delete(_LOCK_KEY)


@shared_task(
    name="apps.games.igdb.tasks.incremental_sync",
    max_retries=2,
    acks_late=True,
    time_limit=3600 * 2,
    soft_time_limit=3600,
)
def incremental_sync() -> None:
    """
    Celery Beat 주기적 증분 동기화
    lookup → 게임 sync 순서로 chain 실행
    """
    from django.core.cache import cache

    if cache.get(_LOCK_KEY):
        logger.info("IGDB incremental_sync: 이미 실행 중, 중복 방지")
        return

    cache.set(_LOCK_KEY, True, timeout=_LOCK_TIMEOUT)
    logger.info("IGDB incremental_sync: lock 설정 완료")

    try:
        task_chain = chain(
            sync_lookup_tables.si(),
            sync_all_games.si(max_pages=50),
        )
        task_chain.apply_async()
        logger.info("IGDB incremental_sync: task chain 실행 완료")
    finally:
        pass
