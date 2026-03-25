from __future__ import annotations

from typing import Any

from apps.games.wikidata.resolvers import resolve_name_ko

from .converters import (
    _parse_cover_url,
    _parse_esrb,
    _parse_rating,
    _parse_website,
    _timestamp_to_date,
    convert_screenshot,
    convert_trailer,
    extract_store_entries,
)


def build_game_list_item(raw: dict[str, Any]) -> dict[str, Any]:
    """
    IGDB raw dict → 게임 목록 응답 항목

    GET /api/v1/games/ 의 results[] 항목과 동일한 shape
    """
    age_ratings = raw.get("age_ratings") or []
    esrb_rating, age_rating_min = _parse_esrb(age_ratings)
    name_ko = resolve_name_ko(raw["id"], raw)

    return {
        "id": raw["id"],
        "slug": raw.get("slug", ""),
        "name": name_ko or raw.get("name", ""),
        "name_ko": name_ko,
        "released": _timestamp_to_date(raw.get("first_release_date")),
        "thumbnail_img_url": _parse_cover_url(raw.get("cover")),
        "rawg_rating": _parse_rating(raw.get("rating")),
        "rawg_ratings_count": raw.get("rating_count") or 0,
        "genres": [
            {"id": g["id"], "name": g.get("name", "")}
            for g in (raw.get("genres") or [])
            if isinstance(g, dict) and g.get("id")
        ],
        "platforms": [
            {"id": p["id"], "name": p.get("name", "")}
            for p in (raw.get("platforms") or [])
            if isinstance(p, dict) and p.get("id")
        ],
        "tags": [
            {"id": k["id"], "name": k.get("name", "")}
            for k in (raw.get("keywords") or [])
            if isinstance(k, dict) and k.get("id")
        ],
        "esrb_rating": esrb_rating,
        "age_rating_min": age_rating_min,
    }


def build_game_detail(raw: dict[str, Any]) -> dict[str, Any]:
    """
    IGDB raw dict → 게임 상세 응답

    GET /api/v1/games/{game_id}/ 와 동일한 shape
    """
    age_ratings = raw.get("age_ratings") or []
    esrb_rating, age_rating_min = _parse_esrb(age_ratings)
    websites = raw.get("websites") or []
    name_ko = resolve_name_ko(raw["id"], raw)

    # 미디어
    media: list[dict[str, Any]] = []
    for ss in raw.get("screenshots") or []:
        if isinstance(ss, dict) and ss.get("image_id"):
            item = convert_screenshot(raw["id"], ss)
            media.append(
                {
                    "type": "screenshot",
                    "media_url": item["media_url"],
                    "video_url_480": None,
                    "video_url_max": None,
                }
            )
    for vid in raw.get("videos") or []:
        if isinstance(vid, dict) and vid.get("video_id"):
            item = convert_trailer(raw["id"], vid)
            media.append(
                {
                    "type": "trailer",
                    "media_url": item["media_url"],
                    "video_url_480": item["video_url_480"],
                    "video_url_max": item["video_url_max"],
                }
            )

    # 스토어
    stores = [{"name": entry["store_slug"], "url": entry["url"]} for entry in extract_store_entries(raw)]

    description = raw.get("summary") or raw.get("storyline") or ""

    return {
        "id": raw["id"],
        "slug": raw.get("slug", ""),
        "name": name_ko or raw.get("name", ""),
        "name_ko": name_ko,
        "description": description,
        "released": _timestamp_to_date(raw.get("first_release_date")),
        "tba": raw.get("status") in (7, 8),  # 7=early_access, 8=unreleased
        "thumbnail_img_url": _parse_cover_url(raw.get("cover")),
        "website": _parse_website(websites),
        "rawg_rating": _parse_rating(raw.get("rating")),
        "rawg_ratings_count": raw.get("rating_count") or 0,
        "rawg_added": raw.get("follows") or 0,
        "esrb_rating": esrb_rating,
        "age_rating_min": age_rating_min,
        "genres": [
            {"id": g["id"], "name": g.get("name", ""), "slug": g.get("slug", "")}
            for g in (raw.get("genres") or [])
            if isinstance(g, dict) and g.get("id")
        ],
        "platforms": [
            {"id": p["id"], "name": p.get("name", "")}
            for p in (raw.get("platforms") or [])
            if isinstance(p, dict) and p.get("id")
        ],
        "tags": [
            {"id": k["id"], "name": k.get("name", "")}
            for k in (raw.get("keywords") or [])
            if isinstance(k, dict) and k.get("id")
        ],
        "media": media,
        "stores": stores,
    }


def build_similar_game_item(raw: dict[str, Any], similarity_score: float) -> dict[str, Any]:
    """
    IGDB raw dict + 유사도 점수 → 유사 게임 응답 항목

    GET /api/v1/games/{game_id}/similar/ 의 results[] 항목
    """
    name_ko = raw.get("name_ko", "")
    return {
        "id": raw["id"],
        "name": name_ko or raw.get("name", ""),
        "name_ko": name_ko,
        "slug": raw.get("slug", ""),
        "thumbnail_img_url": raw.get("thumbnail_img_url", ""),
        "rawg_rating": raw.get("rawg_rating") or 0,
        "similarity_score": similarity_score,
    }
