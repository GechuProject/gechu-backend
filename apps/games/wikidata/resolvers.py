"""
name_ko resolve 로직

우선순위:
    1. 캐시된 name_ko (Redis Hash, fetched_at 있음)
    2. IGDB alternative_names (즉시 사용 가능)
    3. "" → 호출부에서 영어 name fallback

캐시 미스(pending) 시 Celery enqueue
API 요청 중 외부 API 절대 호출하지 않음
"""

from __future__ import annotations

from typing import Any

from apps.games.igdb.converters import extract_korean_from_alt_names
from apps.games.wikidata.client import (
    acquire_enqueue_lock,
    get_failed_count,
    get_name_ko_from_cache,
)

_MAX_FAILED = 3


def resolve_name_ko(igdb_id: int, raw: dict[str, Any]) -> str:
    """
    캐시 히트 시 즉시 반환
    캐시 미스(pending) 시 Celery enqueue 후 alternative_names fallback
    실패 횟수 초과 시 enqueue 안 함
    """
    name_ko = get_name_ko_from_cache(igdb_id)
    if name_ko:
        return name_ko

    slug = raw.get("slug", "")
    if slug:
        _maybe_enqueue(igdb_id, slug)

    return extract_korean_from_alt_names(raw) or ""


def _maybe_enqueue(igdb_id: int, slug: str) -> None:
    if get_failed_count(igdb_id) >= _MAX_FAILED:
        return
    if not acquire_enqueue_lock(igdb_id):
        return

    from apps.games.tasks import fetch_name_ko_task

    fetch_name_ko_task.delay(igdb_id, slug)
