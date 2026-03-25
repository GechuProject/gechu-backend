"""
Wikidata 한국어 게임 이름 클라이언트

Redis Hash 구조:
    Key:   games:name_ko:{igdb_id}
    Field: name_ko       → 한국어 이름 (없으면 빈 문자열)
           chosung       → 초성 (name_ko 있을 때만)
           fetched_at    → ISO 8601 문자열 (조회 완료 시각)
           failed_count  → 실패 횟수 문자열

상태 구분 (fetched_at 기준):
    pending   → 키 없음 (fetched_at 미존재)
    done      → fetched_at 있음 + name_ko != ""
    not_found → fetched_at 있음 + name_ko == ""

enqueue lock:
    Key: games:name_ko_enqueued:{igdb_id}  TTL=1시간
    중복 Celery 태스크 방지용
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)

_SPARQL_URL = "https://query.wikidata.org/sparql"
_TIMEOUT = 10
_REQUEST_INTERVAL = 1.0
_CACHE_TTL = 30 * 24 * 3600  # 30일
_ENQUEUE_LOCK_TTL = 3600  # 1시간
_BULK_CHUNK_SIZE = 50

_KEY_PREFIX = "games:name_ko:"
_LOCK_PREFIX = "games:name_ko_enqueued:"


def _redis() -> Any:
    return get_redis_connection("default")


def _hash_key(igdb_id: int) -> str:
    return f"{_KEY_PREFIX}{igdb_id}"


def _lock_key(igdb_id: int) -> str:
    return f"{_LOCK_PREFIX}{igdb_id}"


# SPARQL ──────────────────────────────────────────────────────────────────


def sparql_query(slug_to_id: dict[str, int]) -> dict[int, str]:
    """
    slug → igdb_id 매핑으로 Wikidata 조회
    Wikidata wdt:P5794는 슬러그로 저장됨
    반환: {igdb_id: name_ko}
    """
    if not slug_to_id:
        return {}

    values = " ".join(f'"{slug}"' for slug in slug_to_id)
    query = f"""
SELECT ?igdbId ?nameKo WHERE {{
  VALUES ?igdbId {{ {values} }}
  ?item wdt:P5794 ?igdbId .
  ?item rdfs:label ?nameKo .
  FILTER(LANG(?nameKo) = "ko")
}}
"""
    try:
        resp = requests.get(
            _SPARQL_URL,
            params={"query": query, "format": "json"},
            headers={"User-Agent": "gechu-backend/1.0 (game localization)"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        bindings: list[dict[str, Any]] = resp.json()["results"]["bindings"]
    except requests.RequestException as e:
        logger.warning("Wikidata 네트워크 오류 (slugs=%s): %s", list(slug_to_id), e)
        return {}
    except (KeyError, ValueError):
        logger.error("Wikidata 응답 파싱 실패 (slugs=%s)", list(slug_to_id), exc_info=True)
        return {}

    result: dict[int, str] = {}
    for row in bindings:
        try:
            slug = row["igdbId"]["value"]
            igdb_id = slug_to_id.get(slug)
            if igdb_id is None:
                continue
            name_ko = row["nameKo"]["value"]
            result[igdb_id] = name_ko
        except (KeyError, ValueError):
            continue
    return result


# Redis 읽기/쓰기 ──────────────────────────────────────────────────────────


def get_name_ko_from_cache(igdb_id: int) -> str | None:
    """
    Redis Hash에서 name_ko 읽기
    fetched_at 없으면 None (pending 상태)
    fetched_at 있고 name_ko 비어있으면 None (not_found)
    """
    r = _redis()
    data = r.hgetall(_hash_key(igdb_id))
    if not data:
        return None
    fetched_at = data.get(b"fetched_at")
    if not fetched_at:
        return None
    name_ko = (data.get(b"name_ko") or b"").decode()
    return name_ko if name_ko else None


def save_name_ko(igdb_id: int, name_ko: str | None, slug: str = "") -> None:
    """
    조회 결과를 Redis Hash에 저장
    name_ko=None 이면 not_found로 기록 (빈 문자열 저장)
    """
    from datetime import UTC, datetime

    from apps.games.chosung import get_chosung_normalized

    r = _redis()
    key = _hash_key(igdb_id)
    chosung = get_chosung_normalized(name_ko) if name_ko else ""
    fetched_at = datetime.now(tz=UTC).isoformat()

    mapping: dict[str, str] = {
        "name_ko": name_ko or "",
        "chosung": chosung,
        "fetched_at": fetched_at,
    }
    if slug:
        mapping["slug"] = slug

    pipe = r.pipeline()
    pipe.hset(key, mapping=mapping)
    pipe.expire(key, _CACHE_TTL)
    pipe.execute()


def increment_failed_count(igdb_id: int) -> int:
    """실패 횟수 증가 후 현재 값 반환"""
    r = _redis()
    key = _hash_key(igdb_id)
    count = r.hincrby(key, "failed_count", 1)
    r.expire(key, _CACHE_TTL)
    return int(count)


def get_failed_count(igdb_id: int) -> int:
    r = _redis()
    val = r.hget(_hash_key(igdb_id), "failed_count")
    return int(val) if val else 0


# enqueue lock ─────────────────────────────────────────────────────────────


def acquire_enqueue_lock(igdb_id: int) -> bool:
    """락 획득 성공 시 True. 이미 enqueue된 경우 False"""
    r = _redis()
    return bool(r.set(_lock_key(igdb_id), "1", nx=True, ex=_ENQUEUE_LOCK_TTL))


def release_enqueue_lock(igdb_id: int) -> None:
    _redis().delete(_lock_key(igdb_id))


# 공개 인터페이스 ───────────────────────────────────────────────────────────


def get_name_ko(igdb_id: int) -> str | None:
    """
    캐시에서 name_ko 읽기
    없으면 None 반환 (Celery enqueue는 호출부 책임)
    """
    return get_name_ko_from_cache(igdb_id)


def get_name_ko_bulk(igdb_ids: list[int]) -> dict[int, str | None]:
    """캐시에서 벌크 읽기. 없는 ID는 None"""
    return {igdb_id: get_name_ko_from_cache(igdb_id) for igdb_id in igdb_ids}


def fetch_and_save_bulk(igdb_id_to_slug: dict[int, str]) -> dict[int, str | None]:
    """
    SPARQL 조회 후 Redis에 저장. Celery worker에서만 호출
    반환: {igdb_id: name_ko or None}

    개선: 실패 시 에디션 suffix 제거 후 재시도
    """
    result: dict[int, str | None] = {}
    items = list(igdb_id_to_slug.items())

    for i in range(0, len(items), _BULK_CHUNK_SIZE):
        chunk = items[i : i + _BULK_CHUNK_SIZE]
        slug_to_id = {slug: igdb_id for igdb_id, slug in chunk}
        fetched = sparql_query(slug_to_id)

        # 실패한 것들 에디션 suffix 제거 후 재시도
        failed_slugs = {}
        for igdb_id, slug in chunk:
            if igdb_id not in fetched:
                cleaned_slug = _remove_edition_suffix(slug)
                if cleaned_slug != slug:
                    failed_slugs[cleaned_slug] = igdb_id

        # 재시도
        if failed_slugs:
            retry_fetched = sparql_query(failed_slugs)
            fetched.update(retry_fetched)

        for igdb_id, slug in chunk:
            name_ko = fetched.get(igdb_id)
            save_name_ko(igdb_id, name_ko, slug=slug)
            result[igdb_id] = name_ko

        if i + _BULK_CHUNK_SIZE < len(items):
            time.sleep(_REQUEST_INTERVAL)

    return result


def _remove_edition_suffix(slug: str) -> str:
    """
    에디션 suffix 제거
    예: 'silent-hill-2--1' -> 'silent-hill-2'
        'assassins-creed-ii-deluxe-edition' -> 'assassins-creed-ii'
    """
    import re

    # 숫자 suffix 제거 (--1, --2 등)
    slug = re.sub(r"--\d+$", "", slug)

    # 에디션 관련 suffix 제거
    edition_suffixes = [
        "-deluxe-edition",
        "-gold-edition",
        "-goty-edition",
        "-game-of-the-year-edition",
        "-complete-edition",
        "-definitive-edition",
        "-ultimate-edition",
        "-special-edition",
        "-collectors-edition",
        "-enhanced-edition",
        "-remastered",
        "-remake",
        "-hd",
        "-collection",
        "-bundle",
        "-legacy-collection",
        "-omega-collection",
    ]

    for suffix in edition_suffixes:
        if slug.endswith(suffix):
            return slug[: -len(suffix)]

    return slug
