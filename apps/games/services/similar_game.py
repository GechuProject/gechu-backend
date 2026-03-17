from typing import Any

from apps.games.igdb import cache as igdb_cache
from apps.games.igdb.response_builder import build_similar_game_item
from apps.recommendations.models import GameSimilarity


class SimilarGameService:
    @staticmethod
    def similar_game(game_id: int, limit: int = 10) -> list[dict[str, Any]]:
        # CF 기반 유사 게임 조회 (score 내림차순)
        similarities = (
            GameSimilarity.objects.filter(igdb_game_id=game_id)
            .order_by("-score")
            .values_list("igdb_similar_game_id", "score")[:limit]
        )

        if not similarities:
            return []

        similar_ids = [s[0] for s in similarities]
        score_map = {s[0]: float(s[1]) for s in similarities}

        # IGDB에서 게임 정보 hydrate
        games = igdb_cache.get_games_by_ids(similar_ids)

        return [build_similar_game_item(g, score_map.get(g["id"], 0.0)) for g in games]
