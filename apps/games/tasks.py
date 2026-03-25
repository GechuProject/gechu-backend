"""
games Celery 태스크

fetch_name_ko_task:
    단건 Wikidata 조회 → Redis 저장
    실패 시 60초 후 최대 3회 재시도

backfill_name_ko_bulk:
    Celery Beat 주기 태스크 (10분마다)
    pending(미조회) 우선, 7일 지난 not_found 재시도 (failed_count < 3)
    Redis SCAN으로 대상 키 수집
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)

_MAX_FAILED = 3
_RETRY_AFTER_DAYS = 7
_BACKFILL_BATCH = 500


@shared_task(bind=True, max_retries=3, rate_limit="1/s")
def fetch_name_ko_task(self: Any, igdb_id: int, slug: str) -> None:
    """
    단건 Wikidata 조회 후 Redis Hash 저장

    lock 해제 정책:
    - 성공 시: 명시적 해제
    - 재시도(Retry) 중: lock 유지 → 중복 enqueue 방지
    - max_retries 초과(최종 실패): MaxRetriesExceededError에서 명시적 해제
    """
    from celery.exceptions import MaxRetriesExceededError

    from apps.games.wikidata.client import (
        increment_failed_count,
        release_enqueue_lock,
        save_name_ko,
        sparql_query,
    )

    try:
        result = sparql_query({slug: igdb_id})
        name_ko = result.get(igdb_id)
    except Exception as exc:
        increment_failed_count(igdb_id)
        logger.warning("fetch_name_ko_task SPARQL 실패: igdb_id=%d", igdb_id, exc_info=True)
        try:
            raise self.retry(countdown=60, exc=exc)
        except MaxRetriesExceededError:
            release_enqueue_lock(igdb_id)
            raise

    try:
        save_name_ko(igdb_id, name_ko, slug=slug)
        logger.info("name_ko 저장 완료: igdb_id=%d, name_ko=%s", igdb_id, name_ko)
    except Exception:
        logger.error("Redis 저장 실패: igdb_id=%d", igdb_id, exc_info=True)
    finally:
        release_enqueue_lock(igdb_id)


@shared_task
def backfill_name_ko_bulk() -> None:
    """
    주기적 백필
    - pending: fetched_at 필드 없는 키
    - retry: fetched_at 있고 name_ko 비어있고 failed_count < 3이고 7일 경과
    """
    from apps.games.wikidata.client import (
        _KEY_PREFIX,
        _hash_key,
        fetch_and_save_bulk,
        increment_failed_count,
    )

    r = get_redis_connection("default")
    retry_threshold = datetime.now(tz=UTC) - timedelta(days=_RETRY_AFTER_DAYS)

    pending_ids: list[int] = []
    retry_ids: list[int] = []
    done = False

    cursor = 0
    while not done:
        cursor, keys = r.scan(cursor, match=f"{_KEY_PREFIX}*", count=200)

        pipe = r.pipeline(transaction=False)
        for key in keys:
            pipe.hgetall(key)
        all_data = pipe.execute()

        for key, data in zip(keys, all_data, strict=False):
            if len(pending_ids) + len(retry_ids) >= _BACKFILL_BATCH * 2:
                done = True
                break
            if not data:
                continue
            try:
                igdb_id = int(key.decode().replace(_KEY_PREFIX, ""))
            except (ValueError, AttributeError):
                continue

            fetched_at_raw = data.get(b"fetched_at")
            name_ko = (data.get(b"name_ko") or b"").decode()
            failed_count = int(data.get(b"failed_count") or b"0")

            if not fetched_at_raw:
                pending_ids.append(igdb_id)
            elif not name_ko and failed_count < _MAX_FAILED:
                try:
                    fetched_at = datetime.fromisoformat(fetched_at_raw.decode())
                    if fetched_at < retry_threshold:
                        retry_ids.append(igdb_id)
                except ValueError:
                    pass

        if cursor == 0:
            break

    all_ids = list(set(pending_ids[:_BACKFILL_BATCH] + retry_ids[:_BACKFILL_BATCH]))
    if not all_ids:
        logger.info("backfill_name_ko_bulk: 처리 대상 없음")
        return

    logger.info(
        "backfill_name_ko_bulk 시작: pending=%d, retry=%d",
        len(pending_ids),
        len(retry_ids),
    )

    # Redis에서 slug 읽어서 매핑 구성 (slug 없는 항목은 skip)
    igdb_id_to_slug: dict[int, str] = {}
    for igdb_id in all_ids:
        slug_raw = r.hget(_hash_key(igdb_id), "slug")
        if slug_raw:
            igdb_id_to_slug[igdb_id] = slug_raw.decode()

    if not igdb_id_to_slug:
        logger.info("backfill_name_ko_bulk: slug 있는 대상 없음")
        return

    results = fetch_and_save_bulk(igdb_id_to_slug)

    for igdb_id, name_ko in results.items():
        if not name_ko:
            increment_failed_count(igdb_id)

    hit = sum(1 for v in results.values() if v)
    logger.info("backfill_name_ko_bulk 완료: 처리=%d, 히트=%d", len(igdb_id_to_slug), hit)
