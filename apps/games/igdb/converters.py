"""
IGDB API 응답(dict) → 각 모델 저장용 dict 변환

설계 원칙:
- 모든 함수는 순수 함수 (I/O 없음, DB 접근 없음)
- convert_*: 모델 생성용 dict 반환
- extract_*: M2M/through 관계 데이터 추출
- 방어적 처리: 키 누락·None·빈 리스트 모두 안전하게 처리

IGDB vs RAWG 주요 차이:
    rating: IGDB는 0~100 → 0~5로 변환 (÷ 20)
    esrb: RAWG slug 방식 → IGDB age_ratings 배열 방식
          category=1: ESRB, category=2: PEGI
          ESRB rating: 1=RP, 2=EC, 3=E, 4=E10, 5=T, 6=M, 7=AO
    cover: image_id → URL 조합 필요
    trailer: YouTube video_id만 제공 (직접 URL 아님)
    screenshot: image_id → URL 조합 필요
    first_release_date: Unix timestamp → date 변환 필요
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from .client import get_image_url


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _timestamp_to_date(ts: int | None) -> date | None:
    """Unix timestamp → date 변환"""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=UTC).date()
    except (OSError, OverflowError, ValueError):
        return None


# IGDB ESRB rating id → DB value 매핑
# category=1이 ESRB, rating 값으로 구분
_IGDB_ESRB_RATING_MAP: dict[int, tuple[str, int]] = {
    1: ("rating_pending", 0),  # RP
    2: ("everyone", 0),  # EC (Early Childhood)
    3: ("everyone", 0),  # E
    4: ("everyone_10_plus", 10),  # E10+
    5: ("teen", 13),  # T
    6: ("mature", 17),  # M
    7: ("adults_only", 18),  # AO
}

# IGDB website URL 패턴 → store slug 매핑
_IGDB_STORE_URL_PATTERNS: dict[str, str] = {
    "store.steampowered.com": "steam",
    "epicgames.com": "epic-games",
    "gog.com": "gog",
    "nintendo.com/store": "nintendo-eshop",
    "store.playstation.com": "playstation-store",
    "xbox.com": "xbox-store",
}


# 룩업 테이블 컨버터 ------------------------------------------


def convert_genre(raw: dict[str, Any]) -> dict[str, Any]:
    """IGDB /genres 항목 → Genre 모델 dict"""
    return {
        "rawg_id": raw["id"],  # igdb_id를 rawg_id 필드에 저장 (모델 재사용)
        "name": raw.get("name", "")[:50],
        "slug": raw.get("slug", "")[:50],
    }


def convert_platform(raw: dict[str, Any]) -> dict[str, Any]:
    """IGDB /platforms 항목 → Platform 모델 dict"""
    logo = raw.get("platform_logo") or {}
    image_id = logo.get("image_id") if isinstance(logo, dict) else None
    icon_url = get_image_url(image_id, "thumb") if image_id else None

    return {
        "rawg_id": raw["id"],
        "name": raw.get("name", "")[:50],
        "slug": raw.get("slug", "")[:50],
        "icon_url": (icon_url or "")[:255] if icon_url else None,
    }


def convert_tag(raw: dict[str, Any]) -> dict[str, Any]:
    """IGDB /keywords 항목 → Tag 모델 dict"""
    return {
        "rawg_id": raw["id"],
        "name": raw.get("name", "")[:50],
        "slug": raw.get("slug", "")[:50],
    }


# ESRB 파싱 헬퍼 ------------------------------------------------------


def _parse_esrb(age_ratings: list[dict[str, Any]] | None) -> tuple[str, int]:
    """
    IGDB age_ratings 배열에서 ESRB(category=1) 파싱

    Returns:
        (db_value, age_rating_min) 튜플
    """
    if not age_ratings:
        return "unknown", 0

    for rating in age_ratings:
        if not isinstance(rating, dict):
            continue
        # category=1: ESRB
        if rating.get("category") == 1:
            rating_id = rating.get("rating")
            if rating_id in _IGDB_ESRB_RATING_MAP:
                return _IGDB_ESRB_RATING_MAP[rating_id]

    return "unknown", 0


def _parse_rating(raw_rating: float | int | None) -> Decimal:
    """
    IGDB rating(0~100) → rawg_rating(0~5) 변환

    IGDB는 0~100 척도, 기존 모델은 0~5 척도이므로 ÷ 20
    """
    if not raw_rating:
        return Decimal("0.00")
    converted = Decimal(str(raw_rating)) / Decimal("20")
    return min(converted, Decimal("5.00"))


def _parse_cover_url(cover: dict[str, Any] | None) -> str:
    """IGDB cover 객체 → 썸네일 URL"""
    if not cover or not isinstance(cover, dict):
        return ""
    image_id = cover.get("image_id")
    if not image_id:
        return ""
    return get_image_url(image_id, "cover_big")


def _parse_website(websites: list[dict[str, Any]] | None) -> str:
    """IGDB websites 배열에서 공식 웹사이트(category=1) URL 추출"""
    if not websites:
        return ""
    for site in websites:
        if isinstance(site, dict) and site.get("category") == 1:
            return str(site.get("url", ""))
    return ""


# 게임 컨버터 -----------------------------------------------------------


def convert_game(raw: dict[str, Any]) -> dict[str, Any]:
    """
    IGDB /games 항목 → Game 모델 dict

    Notes:
        - rawg_id 필드에 IGDB id 저장 (모델 재사용)
        - rating: IGDB 0~100 → 0~5 변환
        - first_release_date: Unix timestamp → date
        - cover.image_id → URL 조합
        - search_vector 의도적 제외
        - is_visible 제외 → 관리자 설정 보존
    """
    age_ratings = raw.get("age_ratings") or []
    esrb_rating, age_rating_min = _parse_esrb(age_ratings)

    rawg_rating = _parse_rating(raw.get("rating"))

    cover = raw.get("cover")
    thumbnail_img_url = _parse_cover_url(cover if isinstance(cover, dict) else None)

    websites = raw.get("websites") or []
    website = _parse_website(websites)

    description = raw.get("summary") or raw.get("storyline") or None

    return {
        "rawg_id": raw["id"],  # IGDB id를 rawg_id 필드에 저장
        "slug": raw.get("slug") or f"igdb-{raw['id']}",
        "name": raw.get("name", ""),
        "description": description,
        "released": _timestamp_to_date(raw.get("first_release_date")),
        "tba": False,  # IGDB는 status 필드로 구분 (4=early_access 등)
        "thumbnail_img_url": thumbnail_img_url,
        "website": website,
        "rawg_rating": rawg_rating,
        "rawg_ratings_count": raw.get("rating_count") or 0,
        "metacritic": None,  # IGDB에 metacritic 필드 없음
        "rawg_added": raw.get("follows") or 0,
        "playtime": 0,  # IGDB에 playtime 필드 없음
        "esrb_rating": esrb_rating,
        "age_rating_min": age_rating_min,
        "rawg_updated": datetime.fromtimestamp(raw["updated_at"], tz=UTC) if raw.get("updated_at") else None,
        "synced_at": _utcnow(),
    }


# 관계 데이터 추출 ------------------------------------------------------


def extract_genre_igdb_ids(raw: dict[str, Any]) -> list[int]:
    """raw에서 장르 IGDB id 목록 추출"""
    genres = raw.get("genres") or []
    return [g["id"] for g in genres if isinstance(g, dict) and g.get("id")]


def extract_keyword_igdb_ids(raw: dict[str, Any]) -> list[int]:
    """raw에서 키워드(태그) IGDB id 목록 추출"""
    keywords = raw.get("keywords") or []
    return [k["id"] for k in keywords if isinstance(k, dict) and k.get("id")]


def extract_platform_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """
    raw의 platforms에서 GamePlatform through 테이블용 데이터 추출

    Returns:
        [{"platform_rawg_id": int, "requirements_minimum": str, "requirements_recommended": str}]
    """
    entries = []
    platforms = raw.get("platforms") or []
    for p in platforms:
        if not isinstance(p, dict):
            continue
        platform_id = p.get("id")
        if not platform_id:
            continue
        entries.append(
            {
                "platform_rawg_id": platform_id,
                "requirements_minimum": "",
                "requirements_recommended": "",
            }
        )
    return entries


def extract_store_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    websites = raw.get("websites") or []
    for site in websites:
        if not isinstance(site, dict):
            continue
        url = site.get("url", "")
        if not url:
            continue
        for pattern, slug in _IGDB_STORE_URL_PATTERNS.items():
            if pattern in url:
                entries.append(
                    {
                        "store_slug": slug,
                        "url": url,
                    }
                )
                break
    return entries


# 미디어 컨버터 ---------------------------------------------------------


def convert_screenshot(game_igdb_id: int, raw: dict[str, Any]) -> dict[str, Any]:
    """
    IGDB screenshots 항목 → GameMedia 모델 dict

    image_id → screenshot_big 사이즈 URL 조합
    """
    image_id = raw.get("image_id", "")
    media_url = get_image_url(image_id, "screenshot_big") if image_id else ""

    return {
        "game_id": game_igdb_id,  # 서비스에서 실제 pk로 교체
        "rawg_id": raw.get("id", 0),
        "type": "screenshot",
        "media_url": media_url,
        "video_url_480": None,
        "video_url_max": None,
        "video_name": None,
    }


def convert_trailer(game_igdb_id: int, raw: dict[str, Any]) -> dict[str, Any]:
    """
    IGDB videos 항목 → GameMedia 모델 dict

    IGDB 트레일러 구조:
        {
            "id": int,
            "name": str,
            "video_id": str,  # YouTube video ID
        }

    YouTube URL 조합:
        thumbnail: https://img.youtube.com/vi/{video_id}/hqdefault.jpg
        480p: https://www.youtube.com/embed/{video_id}  (embed URL)
        max:  https://www.youtube.com/watch?v={video_id}
    """
    video_id = raw.get("video_id", "")
    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else ""
    embed_url = f"https://www.youtube.com/embed/{video_id}" if video_id else None
    watch_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None

    return {
        "game_id": game_igdb_id,  # 서비스에서 실제 pk로 교체
        "rawg_id": raw.get("id", 0),
        "type": "trailer",
        "media_url": thumbnail_url,
        "video_url_480": embed_url,
        "video_url_max": watch_url,
        "video_name": raw.get("name") or None,
    }
