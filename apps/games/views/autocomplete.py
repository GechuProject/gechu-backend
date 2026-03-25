"""
게임 자동완성 API

GET /api/v1/games/autocomplete/?q=디

검색 대상: Redis에 name_ko가 저장된 게임 (Wikidata 조회 완료된 것들)
검색 방식: prefix startswith (name_ko, chosung, name 순)
결과: 최대 10개, 1분 캐시

초성 검색 예시:
    q=ㄷㄱ → "디 키" 같은 초성 매칭
    q=디아 → name_ko prefix 매칭
    q=Diab → 영어 name prefix 매칭 (IGDB 캐시에서)
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from django.core.cache import cache
from django_redis import get_redis_connection
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.games.chosung import get_chosung_normalized
from apps.games.wikidata.client import _KEY_PREFIX

logger = logging.getLogger(__name__)

_AUTOCOMPLETE_TTL = 60  # 1분
_MAX_RESULTS = 10
_SCAN_COUNT = 500  # SCAN 한 번에 가져올 키 수
_MAX_SCAN_ITERATIONS = 50  # SCAN 최대 반복 횟수


@extend_schema(
    summary="게임 자동완성",
    parameters=[OpenApiParameter("q", str, description="검색어 (한글, 초성, 영어)")],
    responses={200: {"type": "array"}},
    tags=["games"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def autocomplete_games(request: Request) -> Response:
    query = request.GET.get("q", "").strip()
    if not query:
        return Response([])

    cache_key = f"games:autocomplete:{hashlib.md5(query.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    results = _search(query)
    cache.set(cache_key, results, _AUTOCOMPLETE_TTL)
    return Response(results)


def _search(query: str) -> list[dict[str, Any]]:
    """
    Redis SCAN으로 games:name_ko:* 키를 순회하며 prefix 매칭.
    우선순위: name_ko prefix(3) > chosung prefix(2) > name prefix(1)
    """
    r = get_redis_connection("default")
    chosung_query = get_chosung_normalized(query)
    query_lower = query.lower()

    matches: list[tuple[int, dict[str, Any]]] = []  # (priority, item)

    cursor = 0
    iterations = 0
    while iterations < _MAX_SCAN_ITERATIONS:
        cursor, keys = r.scan(cursor, match=f"{_KEY_PREFIX}*", count=_SCAN_COUNT)
        iterations += 1

        pipe = r.pipeline(transaction=False)
        for key in keys:
            pipe.hgetall(key)
        all_data = pipe.execute()

        for key, data in zip(keys, all_data, strict=False):
            if not data:
                continue
            if not data.get(b"fetched_at"):
                continue

            name_ko = (data.get(b"name_ko") or b"").decode()
            chosung = (data.get(b"chosung") or b"").decode()

            try:
                igdb_id = int(key.decode().replace(_KEY_PREFIX, ""))
            except (ValueError, AttributeError):
                continue

            priority = 0
            if name_ko and name_ko.startswith(query):
                priority = 3
            elif chosung_query and chosung.startswith(chosung_query):
                priority = 2

            # English name matching for games with empty name_ko or when no Korean match found
            if priority == 0 or not name_ko:
                # Try to get English name from igdb:game:* cache
                game_data = r.get(f"igdb:game:{igdb_id}")
                if game_data:
                    try:
                        game = json.loads(game_data)
                        english_name = game.get("name", "").lower()
                        if english_name.startswith(query_lower):
                            # If we already have a Korean match (priority 2 or 3), keep it
                            # Otherwise set priority to 1 for English match
                            if priority == 0:
                                priority = 1  # Lower priority than Korean matches
                    except (json.JSONDecodeError, KeyError):
                        pass

            if priority == 0:
                continue

            matches.append(
                (
                    priority,
                    {
                        "id": igdb_id,
                        "name_ko": name_ko,
                        "chosung": chosung,
                        "priority": priority,
                    },
                )
            )

        if cursor == 0 or len(matches) >= _MAX_RESULTS * 5:
            break

    # 영어 name prefix 매칭은 IGDB 캐시(igdb:game:*)에서 보완
    _enrich_with_igdb_cache(r, query_lower, matches)

    # 정렬: priority 내림차순
    matches.sort(key=lambda x: x[0], reverse=True)

    seen_ids: set[int] = set()
    results = []
    for _, item in matches:
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        results.append(
            {
                "id": item["id"],
                "name": item.get("name", ""),
                "name_ko": item["name_ko"],
                "thumbnail_img_url": item.get("thumbnail_img_url", ""),
            }
        )
        if len(results) >= _MAX_RESULTS:
            break

    return results


def _enrich_with_igdb_cache(r: Any, query_lower: str, matches: list[tuple[int, dict[str, Any]]]) -> None:
    """
    IGDB 게임 캐시(igdb:game:*)에서 영어 name prefix 매칭 보완.
    이미 name_ko 매칭된 ID는 skip.
    """
    existing_ids = {item[1]["id"] for item in matches}

    cursor = 0
    added = 0
    iterations = 0
    while iterations < _MAX_SCAN_ITERATIONS and added < _MAX_RESULTS:
        cursor, keys = r.scan(cursor, match="igdb:game:*", count=200)
        iterations += 1

        pipe = r.pipeline(transaction=False)
        for key in keys:
            pipe.get(key)
        all_data = pipe.execute()

        for data in all_data:
            if not data:
                continue
            try:
                game = json.loads(data)
                igdb_id = game.get("id")
                name = game.get("name", "")
                if igdb_id in existing_ids:
                    continue
                if name.lower().startswith(query_lower):
                    matches.append(
                        (
                            1,
                            {
                                "id": igdb_id,
                                "name": name,
                                "name_ko": game.get("name_ko", ""),
                                "thumbnail_img_url": game.get("thumbnail_img_url", ""),
                                "priority": 1,
                            },
                        )
                    )
                    existing_ids.add(igdb_id)
                    added += 1
            except (ValueError, KeyError, TypeError):
                continue

        if cursor == 0:
            break
