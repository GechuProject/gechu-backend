from typing import Any

from apps.games.igdb import cache as igdb_cache

# IGDB 정렬 매핑: API 쿼리 파라미터 → IGDB sort 필드
_ORDERING_MAP: dict[str, str] = {
    "rawg_rating": "rating asc",
    "-rawg_rating": "rating desc",
    "released": "first_release_date asc",
    "-released": "first_release_date desc",
    "rawg_added": "follows asc",
    "-rawg_added": "follows desc",
}


class GameService:
    @staticmethod
    def list_games(
        *,
        search: str | None = None,
        genre_ids: list[int] | None = None,
        platform_ids: list[int] | None = None,
        tag_ids: list[int] | None = None,
        ordering: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        igdb_sort = _ORDERING_MAP.get(ordering or "-rawg_rating", "rating desc")
        offset = (page - 1) * page_size

        # limit+1 조회하여 has_next 판단
        results = igdb_cache.search_games(
            query=search,
            genre_ids=genre_ids,
            platform_ids=platform_ids,
            tag_ids=tag_ids,
            sort=igdb_sort,
            limit=page_size + 1,
            offset=offset,
        )

        return results

    @staticmethod
    def top_n_by_genre(genre_name: str, top_n: int = 10, sort: str = "-rawg_rating") -> list[dict[str, Any]]:
        igdb_sort = _ORDERING_MAP.get(sort, "rating desc")

        # 캐시에서 장르 이름 -> id 조회
        genre_id = igdb_cache.get_genre_id_by_name(genre_name)
        if not genre_id:
            return []

        results = igdb_cache.search_games(genre_ids=[genre_id], sort=igdb_sort, limit=top_n)
        return results
