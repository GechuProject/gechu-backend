from typing import Any, cast

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models import Game
from apps.games.serializers import SimilarGameResponseSerializer
from apps.recommendations.models import GameSimilarity


class SimilarGameService:
    @staticmethod
    def similar_game(game_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """
        특정 게임(game_id)의 유사 게임 목록 조회
        - limit: 최대 반환 개수 (기본 10)
        """

        # 1. 대상 게임 존재 확인
        try:
            game = Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            raise CustomAPIException(ErrorMessages.GAME_NOT_FOUND) from None

        # 2. 유사 게임 조회 (score 내림차순, limit 적용)
        similar_qs = GameSimilarity.objects.filter(game=game).select_related("similar_game").order_by("-score")[:limit]

        # 3. 직렬화 준비
        # GameSimilarity -> {similar_game 필드 + score 필드} 형태로 매핑
        results = []
        for sim in similar_qs:
            results.append(
                cast(
                    dict[str, Any],
                    SimilarGameResponseSerializer(
                        {
                            "id": sim.similar_game.id,
                            "name": sim.similar_game.name,
                            "slug": sim.similar_game.slug,
                            "thumbnail_img_url": sim.similar_game.thumbnail_img_url,
                            "rawg_rating": sim.similar_game.rawg_rating,
                            "score": float(sim.score),  # similarity_score로 매핑
                        }
                    ).data,
                )
            )

        return results
