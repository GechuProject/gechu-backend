from apps.games.models.game import Game

class GameService:
    @staticmethod
    def list_games(
        search: str | None = None,
        genre_ids: list[int] | None = None,
        platform_ids: list[int] | None = None,
        tag_ids: list[int] | None = None,
        esrb_rating: str | None = None,
        ordering: str | None = "-rawg_rating",
    ):
        qs = Game.objects.filter(is_visible=True)

        # 검색
        if search:
            qs = qs.filter(name__icontains=search)

        # 장르 필터
        if genre_ids:
            qs = qs.filter(genres__id__in=genre_ids).distinct()

        # 플랫폼 필터
        if platform_ids:
            qs = qs.filter(platforms__id__in=platform_ids).distinct()

        # 태그 필터
        if tag_ids:
            qs = qs.filter(tags__id__in=tag_ids).distinct()

        # ESRB 필터
        if esrb_rating:
            qs = qs.filter(esrb_rating=esrb_rating)

        # 정렬
        if ordering:
            qs = qs.order_by(ordering)

        return qs