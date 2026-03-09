from typing import Any, cast

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models import Game
from apps.games.serializers import SimilarGameResponseSerializer
from apps.recommendations.models import GameSimilarity


class SimilarGameService:
    @staticmethod
    def similar_game(game_id: int, limit: int = 10) -> list[dict[str, Any]]:

        # 유사 게임 조회 (score 내림차순, limit 적용)
        similar_qs = (
            GameSimilarity.objects.filter(game_id=game_id).select_related("similar_game").order_by("-score")[:limit]
        )

        if not similar_qs and not Game.objects.filter(id=game_id).exists():
            raise CustomAPIException(ErrorMessages.GAME_NOT_FOUND)

        serializer = SimilarGameResponseSerializer(similar_qs, many=True)

        return cast(list[dict[str, Any]], serializer.data)
