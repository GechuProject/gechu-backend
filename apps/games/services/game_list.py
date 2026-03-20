from typing import Any

from apps.games.igdb import cache as igdb_cache
from apps.preferences.models import UserGameAffinity
from apps.users.models import User

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
    def attach_is_saved(results: list[dict[str, Any]], user: User | None = None) -> list[dict[str, Any]]:
        """
        게임 리스트에 is_saved 필드 추가 (찜 여부)
        """

        if not user or not user.is_authenticated:
            for game in results:
                game["is_saved"] = False
            return results

        game_ids = [game["id"] for game in results]

        # 한 번에 조회 (N+1 방지)
        affinities = UserGameAffinity.objects.filter(
            user=user,
            igdb_game_id__in=game_ids,
        )

        # {게임ID: is_saved} 매핑
        affinity_map = {affinity.igdb_game_id: affinity.is_saved for affinity in affinities}

        # 결과에 붙이기
        for game in results:
            game["is_saved"] = affinity_map.get(game["id"], False)

        return results

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
        user: User | None = None,
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

        return GameService.attach_is_saved(results, user)

    @staticmethod
    def top_n_by_genre(
        genre_name: str,
        top_n: int = 10,
        sort: str = "-rawg_rating",
        user: User | None = None,
    ) -> list[dict[str, Any]]:
        igdb_sort = _ORDERING_MAP.get(sort, "rating desc")

        # 캐시에서 장르 이름 -> id 조회
        genre_id = igdb_cache.get_genre_id_by_name(genre_name)
        if not genre_id:
            return []

        results = igdb_cache.search_games(genre_ids=[genre_id], sort=igdb_sort, limit=top_n)

        return GameService.attach_is_saved(results, user)
