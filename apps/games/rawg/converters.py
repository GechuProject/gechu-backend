"""
RAWG API 응답(dict) → 각 모델 저장용 dict 변환

설계 원칙:
- 모든 함수는 순수 함수 (I/O 없음, DB 접근 없음)
- convert_*: 모델 생성용 dict 반환
- extract_*: M2M/through 관계 데이터 추출
- 방어적 처리: 키 누락·None·빈 리스트 모두 안전하게 처리

RAWG 응답 구조 참고:
    /games → list_raw  (간략 정보)
    /games/{id} → detail_raw (description, website, stores 포함)
    두 응답을 병합하여 convert_game()에 전달

수정 이력:
    - convert_platform: icon_url → None (RAWG에 플랫폼 아이콘 전용 필드 없음)
    - convert_store: icon_url [:255] 슬라이싱으로 max_length 방어
    - convert_game: slug 없을 때 f"rawg-{id}" fallback (unique 제약 방어)
    - convert_game: search_vector 의도적 제외 (별도 업데이트 예정)
    - convert_game: rawg_rating 5.00 상한 적용
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


# ── ESRB 매핑 ────────────────────────────────────────────────────────────

# RAWG ESRB slug → Game.EsrbRating DB value
_RAWG_ESRB_SLUG_TO_DB: dict[str, str] = {
    "everyone": "everyone",
    "everyone-10-plus": "everyone_10_plus",
    "teen": "teen",
    "mature": "mature",
    "adults-only": "adults_only",
    "rating-pending": "rating_pending",
}

# EsrbRating DB value → 최소 연령
_ESRB_AGE_MAP: dict[str, int] = {
    "everyone": 0,
    "everyone_10_plus": 10,
    "teen": 13,
    "mature": 17,
    "adults_only": 18,
    "rating_pending": 0,
    "unknown": 0,
}


# ── 룩업 테이블 컨버터 ─────────────────────────────────────────────────────


def convert_genre(raw: dict[str, Any]) -> dict[str, Any]:
    """RAWG /genres 항목 → Genre 모델 dict"""
    return {
        "rawg_id": raw["id"],
        "name": raw["name"],
        "slug": raw["slug"],
    }


def convert_platform(raw: dict[str, Any]) -> dict[str, Any]:
    """
    RAWG /platforms 항목 → Platform 모델 dict

    icon_url: RAWG API에 플랫폼 아이콘 전용 필드가 없으므로 None
              (image_background는 배경 이미지라 의미 불일치)
              클라이언트에서 기본 아이콘으로 처리
    """
    return {
        "rawg_id": raw["id"],
        "name": raw["name"],
        "slug": raw["slug"],
        "icon_url": None,
    }


def convert_tag(raw: dict[str, Any]) -> dict[str, Any]:
    """RAWG /tags 항목 → Tag 모델 dict"""
    return {
        "rawg_id": raw["id"],
        "name": raw["name"],
        "slug": raw["slug"],
    }


def convert_store(raw: dict[str, Any]) -> dict[str, Any]:
    """
    RAWG /stores 항목 → ExternalStore 모델 dict

    icon_url: image_background URL이 255자를 초과할 수 있으므로 슬라이싱
    """
    return {
        "rawg_id": raw["id"],
        "name": raw["name"],
        "slug": raw["slug"],
        "domain": raw.get("domain", ""),
        "icon_url": (raw.get("image_background") or "")[:255],
    }


# ── ESRB 파싱 헬퍼 ────────────────────────────────────────────────────────


def _parse_esrb(raw_esrb: dict[str, Any] | None) -> tuple[str, int]:
    """
    RAWG esrb_rating 필드 파싱

    Returns:
        (db_value, age_rating_min) 튜플
        예: ("mature", 17)
    """
    if not raw_esrb:
        return "unknown", 0
    slug = raw_esrb.get("slug", "")
    db_value = _RAWG_ESRB_SLUG_TO_DB.get(slug, "unknown")
    age_min = _ESRB_AGE_MAP.get(db_value, 0)
    return db_value, age_min


def _parse_rawg_updated(raw: dict[str, Any]) -> datetime | None:
    """
    RAWG updated 필드(ISO 문자열) → timezone-aware datetime
    파싱 실패 시 None 반환
    """
    updated_str: str | None = raw.get("updated")
    if not updated_str:
        return None
    try:
        dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, AttributeError):
        return None


# ── 게임 컨버터 ───────────────────────────────────────────────────────────


def convert_game(list_raw: dict[str, Any], detail_raw: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    RAWG /games 목록 항목 + /games/{id} 상세 항목 → Game 모델 dict

    Args:
        list_raw: /games 응답의 단일 게임 dict (필수)
        detail_raw: /games/{id} 응답 dict (선택. None이면 목록 데이터만 사용)

    Notes:
        - rawg_rating 상한: 5.00 (RAWG 척도, max_digits=3 방어)
        - slug 없을 때 f"rawg-{id}" fallback (unique 제약 방어)
        - search_vector 의도적 제외 → null로 저장, 별도 업데이트 예정
        - age_rating_min: convert_game()에서 직접 계산
          (bulk_create는 Model.save()를 호출하지 않으므로 여기서 처리)
        - is_visible 제외 → 관리자 설정 보존
        - synced_at 항상 현재 UTC 시각
    """
    detail = detail_raw or {}

    esrb_rating, age_rating_min = _parse_esrb(list_raw.get("esrb_rating"))

    # rawg_rating: RAWG는 0~5 척도, max_digits=3(최대 9.99) 방어용 5.00 상한
    raw_rating = list_raw.get("rating") or 0
    rawg_rating = min(Decimal(str(raw_rating)), Decimal("5.00"))

    return {
        "rawg_id": list_raw["id"],
        "slug": list_raw.get("slug") or f"rawg-{list_raw['id']}",
        "name": list_raw.get("name", ""),
        "description": detail.get("description_raw") or detail.get("description") or None,
        "released": list_raw.get("released") or None,
        "tba": list_raw.get("tba", False),
        "thumbnail_img_url": list_raw.get("background_image") or "",
        "website": detail.get("website") or "",
        "rawg_rating": rawg_rating,
        "rawg_ratings_count": list_raw.get("ratings_count") or 0,
        "metacritic": list_raw.get("metacritic") or None,
        "rawg_added": list_raw.get("added") or 0,
        "playtime": list_raw.get("playtime") or 0,
        "esrb_rating": esrb_rating,
        "age_rating_min": age_rating_min,
        "rawg_updated": _parse_rawg_updated(list_raw),
        "synced_at": _utcnow(),
        # is_visible 제외: 관리자 설정 보존 (bulk_create update_fields에서도 제외)
        # search_vector 제외: null 저장 후 별도 업데이트 예정
    }


# ── 관계 데이터 추출 ──────────────────────────────────────────────────────


def extract_genre_rawg_ids(list_raw: dict[str, Any]) -> list[int]:
    """list_raw에서 장르 rawg_id 목록 추출"""
    return [g["id"] for g in list_raw.get("genres", []) if g.get("id")]


def extract_tag_rawg_ids(list_raw: dict[str, Any]) -> list[int]:
    """list_raw에서 태그 rawg_id 목록 추출"""
    return [t["id"] for t in list_raw.get("tags", []) if t.get("id")]


def extract_platform_entries(list_raw: dict[str, Any]) -> list[dict[str, Any]]:
    """
    list_raw의 platforms 항목에서 GamePlatform through 테이블용 데이터 추출

    Returns:
        [{"platform_rawg_id": int, "requirements_minimum": str, "requirements_recommended": str}]
    """
    entries = []
    for item in list_raw.get("platforms", []):
        platform = item.get("platform", {})
        platform_id = platform.get("id")
        if not platform_id:
            continue  # id 없는 항목 skip
        reqs: dict[str, Any] = item.get("requirements", {}) or {}
        entries.append(
            {
                "platform_rawg_id": platform_id,
                "requirements_minimum": reqs.get("minimum", ""),
                "requirements_recommended": reqs.get("recommended", ""),
            }
        )
    return entries


def extract_store_entries(detail_raw: dict[str, Any]) -> list[dict[str, Any]]:
    """
    detail_raw의 stores 항목에서 GameStore through 테이블용 데이터 추출

    Returns:
        [{"store_rawg_id": int, "url": str}]
    """
    entries = []
    for item in detail_raw.get("stores", []):
        store = item.get("store", {})
        store_id = store.get("id")
        if not store_id:
            continue  # id 없는 항목 skip
        entries.append(
            {
                "store_rawg_id": store_id,
                "url": item.get("url", ""),
            }
        )
    return entries


# ── 미디어 컨버터 ─────────────────────────────────────────────────────────


def convert_screenshot(game_rawg_id: int, raw: dict[str, Any]) -> dict[str, Any]:
    """
    RAWG /games/{id}/screenshots 항목 → GameMedia 모델 dict

    Notes:
        game_id는 DB pk가 아닌 rawg_id로 임시 저장
        서비스 레이어(_sync_game_media)에서 실제 game.id로 교체합니다
    """
    return {
        "game_id": game_rawg_id,  # 서비스에서 실제 pk로 교체
        "rawg_id": raw["id"],
        "type": "screenshot",
        "media_url": raw.get("image", ""),
        "video_url_480": None,
        "video_url_max": None,
        "video_name": None,
    }


def convert_trailer(game_rawg_id: int, raw: dict[str, Any]) -> dict[str, Any]:
    """
    RAWG /games/{id}/movies 항목 → GameMedia 모델 dict

    RAWG 트레일러 구조:
        {
            "id": int,
            "name": str,
            "preview": str,   # 썸네일 URL
            "video_url": {
                "480": str,   # 480p 비디오 URL
                "max": str,   # 최고화질 비디오 URL
            }
        }
    """
    data: dict[str, Any] = raw.get("data", {}) or {}
    return {
        "game_id": game_rawg_id,  # 서비스에서 실제 pk로 교체
        "rawg_id": raw["id"],
        "type": "trailer",
        "media_url": raw.get("preview", ""),
        "video_url_480": data.get("data_480") or None,
        "video_url_max": data.get("max") or None,
        "video_name": raw.get("name") or None,
    }
