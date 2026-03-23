from typing import Any

from django.contrib.auth.models import AnonymousUser

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.igdb import cache as igdb_cache
from apps.games.services.game_list import GameService
from apps.users.models import User


class GameDetailService:
    @staticmethod
    def detail_game(
        *,
        game_id: int,
        user: User | AnonymousUser | None = None,
    ) -> dict[str, Any]:
        game = igdb_cache.get_game_detail(game_id)

        if game["age_rating_min"] >= 18:
            if not user or not user.is_authenticated or not getattr(user, "is_adult_verified", False):
                raise CustomAPIException(ErrorMessages.ADULT_VERIFICATION_REQUIRED)

        result = GameService.attach_is_saved([game], user if isinstance(user, User) else None)
        return result[0]
