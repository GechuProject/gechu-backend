from typing import Any

from apps.games.igdb import cache as igdb_cache
from apps.games.models import Genre
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
    def filter_adult_games(results: list[dict[str, Any]], user: User | None = None) -> list[dict[str, Any]]:
        """
        성인 인증 안 된 유저에게 성인 게임 노출 X
        """
        if user and user.is_authenticated and getattr(user, "is_adult_verified", False):
            return results  # 성인 인증 완료 유저는 전체 반환

        return [game for game in results if game.get("age_rating_min", 0) < 18]

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

        results = GameService.attach_is_saved(results, user)
        return GameService.filter_adult_games(results, user)

    @staticmethod
    def top_n_by_genre(
        genre_name: str,
        top_n: int = 10,
        sort: str = "-rawg_rating",
        user: User | None = None,
    ) -> list[dict[str, Any]]:
        igdb_sort = _ORDERING_MAP.get(sort, "rating desc")

        # DB에서 한국어 장르명으로 igdb_id 조회
        genre = Genre.objects.filter(name=genre_name).first()
        if not genre or not genre.igdb_id:
            return []

        # rating_count >= 100, 평점순 top10
        results = igdb_cache.search_games_by_igdb_genre_id(
            igdb_genre_id=genre.igdb_id,
            sort=igdb_sort,
            limit=top_n,
        )

        results = GameService.attach_is_saved(results, user)
        return GameService.filter_adult_games(results, user)
