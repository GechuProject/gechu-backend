from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, cast

from django.conf import settings
from django.core.cache import cache

from apps.games.models import Platform

from .client import get_igdb_client
from .exceptions import IgdbRateLimitError, IgdbServerError
from .response_builder import build_game_detail, build_game_list_item

logger = logging.getLogger(__name__)

_GAME_TTL = 3600
_SEARCH_TTL = 900
_LOOKUP_TTL = 86400


def _cache_key_game(igdb_id: int) -> str:
    return f"igdb:game:{igdb_id}"


def _cache_key_search(params: dict[str, Any]) -> str:
    raw = json.dumps(params, sort_keys=True, default=str)
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"igdb:search:{h}"


def fetch_all_igdb_genres() -> dict[str, int]:
    """IGDB에서 장르 목록을 가져와서 {장르이름: 장르ID} 매핑 반환"""
    client = get_igdb_client()
    raw_genres = client._post("genres", "fields id,name;limit 50;")
    return {genre["name"]: genre["id"] for genre in raw_genres}


def get_genre_id_by_name(name: str) -> int | None:
    """
    캐시에서 장르 이름 → IGDB 장르 ID 조회
    캐시에 없으면 fetch_all_igdb_genres() 호출 후 캐시 저장
    """
    genre_map = cache.get(settings.IGDB_GENRE_MAP_CACHE_KEY)
    if genre_map is None:
        genre_map = fetch_all_igdb_genres()
        cache.set(
            settings.IGDB_GENRE_MAP_CACHE_KEY,
            genre_map,
            settings.IGDB_GENRE_MAP_CACHE_TTL,
        )

    genre_map = cast(dict[str, int], genre_map)

    genre_id = genre_map.get(name)
    return int(genre_id) if genre_id is not None else None


def _resolve_genre_filters(genre_ids: list[int]) -> dict[str, list[int]]:
    """DB Genre PK 리스트 → IGDB 타입별 ID 분류"""
    from apps.games.models import Genre

    if not genre_ids:
        return {}

    rows = Genre.objects.filter(id__in=genre_ids).values_list("igdb_id", "igdb_type")
    result: dict[str, list[int]] = {}
    for igdb_id, igdb_type in rows:
        result.setdefault(igdb_type, []).append(igdb_id)
    return result


def _resolve_tag_filters(tag_ids: list[int]) -> dict[str, list[int]]:
    """DB Tag PK 리스트 → IGDB 타입별 ID 분류"""
    from apps.games.models import Tag

    if not tag_ids:
        return {}

    rows = Tag.objects.filter(id__in=tag_ids).values_list("igdb_id", "igdb_type")
    result: dict[str, list[int]] = {}
    for igdb_id, igdb_type in rows:
        result.setdefault(igdb_type, []).append(igdb_id)
    return result


def _resolve_platform_filters(platform_ids: list[int]) -> list[int]:
    """DB Platform PK 리스트 → IGDB platform ID 리스트"""

    if not platform_ids:
        return []

    return list(Platform.objects.filter(id__in=platform_ids).values_list("igdb_id", flat=True))


def get_game_detail(igdb_id: int) -> dict[str, Any]:
    key = _cache_key_game(igdb_id)
    cached: dict[str, Any] | None = cache.get(key)
    if cached is not None:
        return cached

    client = get_igdb_client()
    raw = client.get_game(igdb_id)
    result: dict[str, Any] = build_game_detail(raw)

    cache.set(key, result, _GAME_TTL)
    return result


def search_games(
    *,
    query: str | None = None,
    genre_ids: list[int] | None = None,
    platform_ids: list[int] | None = None,
    tag_ids: list[int] | None = None,
    sort: str = "rating desc",
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "genre_ids": genre_ids,
        "platform_ids": platform_ids,
        "tag_ids": tag_ids,
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }
    key = _cache_key_search(params)

    cached: list[dict[str, Any]] | None = cache.get(key)
    if cached is not None:
        return cached

    genre_filters = _resolve_genre_filters(genre_ids or [])
    tag_filters = _resolve_tag_filters(tag_ids or [])
    igdb_platform_ids = _resolve_platform_filters(platform_ids or [])

    client = get_igdb_client()
    try:
        raw_list = client.search_games(
            query=query,
            genre_ids=genre_filters.get("genre"),
            platform_ids=igdb_platform_ids or None,
            tag_ids=tag_filters.get("keyword"),
            theme_ids=(genre_filters.get("theme", []) + tag_filters.get("theme", [])) or None,
            game_mode_ids=(genre_filters.get("game_mode", []) + tag_filters.get("game_mode", [])) or None,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except (IgdbRateLimitError, IgdbServerError):
        logger.warning("IGDB 호출 실패, stale 캐시 반환 시도")
        stale: list[dict[str, Any]] | None = cache.get(key)
        if stale is not None:
            return stale
        raise

    results = [build_game_list_item(raw) for raw in raw_list]
    cache.set(key, results, _SEARCH_TTL)
    return results


def search_games_by_igdb_genre_id(
    *,
    igdb_genre_id: int,
    sort: str = "rating desc",
    limit: int = 10,
    min_rating_count: int = 100,
    min_rating: float = 70,
    min_release_date: int = int(datetime(2021, 1, 1).timestamp()),
) -> list[dict[str, Any]]:
    params = {
        "igdb_genre_id": igdb_genre_id,
        "sort": sort,
        "limit": limit,
        "min_rating_count": min_rating_count,
        "min_rating": min_rating,
        "min_release_date": min_release_date,
    }
    key = _cache_key_search(params)

    cached: list[dict[str, Any]] | None = cache.get(key)
    if cached is not None:
        return cached

    client = get_igdb_client()
    try:
        raw_list = client.search_games(
            genre_ids=[igdb_genre_id],
            sort=sort,
            limit=limit,
            min_rating_count=min_rating_count,
            min_rating=min_rating,
            min_release_date=min_release_date,
        )
    except (IgdbRateLimitError, IgdbServerError):
        logger.warning("IGDB 호출 실패, stale 캐시 반환 시도")
        stale: list[dict[str, Any]] | None = cache.get(key)
        if stale is not None:
            return stale
        raise

    results = [build_game_list_item(raw) for raw in raw_list]
    cache.set(key, results, _SEARCH_TTL)
    return results


def get_games_by_ids(igdb_ids: list[int]) -> list[dict[str, Any]]:
    if not igdb_ids:
        return []

    results: dict[int, dict[str, Any]] = {}
    missing_ids: list[int] = []

    for igdb_id in igdb_ids:
        cached = cache.get(_cache_key_game(igdb_id))
        if cached is not None:
            results[igdb_id] = cached
        else:
            missing_ids.append(igdb_id)

    if missing_ids:
        client = get_igdb_client()
        raw_list = client.get_games_by_ids(missing_ids)
        for raw in raw_list:
            detail = build_game_detail(raw)
            igdb_id = raw["id"]
            results[igdb_id] = detail
            cache.set(_cache_key_game(igdb_id), detail, _GAME_TTL)

    return [results[igdb_id] for igdb_id in igdb_ids if igdb_id in results]
