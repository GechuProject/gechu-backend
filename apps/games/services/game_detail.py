from django.contrib.auth.models import AnonymousUser

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models import Game
from apps.users.models import User


class GameDetailService:
    @staticmethod
    def detail_game(
        *,
        game_id: int,
        user: User | AnonymousUser | None = None,
    ) -> Game:

        game = (
            Game.objects.prefetch_related(
                "game_genres__genre",
                "game_tags__tag",
                "game_platforms__platform",
                "media",
                "game_stores__store",
            )
            .filter(pk=game_id, is_visible=True)
            .first()
        )

        if game is None:
            raise CustomAPIException(ErrorMessages.GAME_NOT_FOUND)

        if game.age_rating_min >= 18:
            if not user or not user.is_authenticated or not getattr(user, "is_adult_verified", False):
                raise CustomAPIException(ErrorMessages.ADULT_VERIFICATION_REQUIRED)

        return game
