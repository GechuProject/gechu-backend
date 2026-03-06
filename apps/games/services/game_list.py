from django.contrib.auth.models import AnonymousUser
from django.db.models.query import QuerySet

from apps.games.models.catalog import Game
from apps.users.models import User


class GameService:
    @staticmethod
    def list_games(
        *,
        user: User | AnonymousUser | None = None,
        search: str | None = None,
        genre_ids: list[int] | None = None,
        platform_ids: list[int] | None = None,
        tag_ids: list[int] | None = None,
        esrb_rating: str | None = None,
        ordering: str | None = None,
    ) -> QuerySet[Game]:
        qs = Game.objects.filter(is_visible=True)

        # 검색
        if search:
            qs = qs.filter(name__icontains=search)

        # 장르 필터
        if genre_ids:
            qs = qs.filter(game_genres__genre_id__in=genre_ids)

        # 플랫폼 필터
        if platform_ids:
            qs = qs.filter(game_platforms__platform_id__in=platform_ids)

        # 태그 필터
        if tag_ids:
            qs = qs.filter(game_tags__tag_id__in=tag_ids)

        # ESRB 필터
        if esrb_rating:
            qs = qs.filter(esrb_rating=esrb_rating)

        # 성인 필터
        if user is None or not user.is_authenticated or not user.is_adult_verified:
            qs = qs.filter(age_rating_min__lt=18)

        qs = qs.distinct()

        # 게임 목록 가져올 때 가져올것들
        qs = qs.prefetch_related(
            "game_genres__genre",
            "game_platforms__platform",
            "game_tags__tag",
        )

        # 정렬
        qs = qs.order_by(ordering or "-rawg_rating")

        return qs
