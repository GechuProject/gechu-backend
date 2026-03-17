from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.recommendations.models import GameSimilarity

IGDB_GAME_1 = 1001
IGDB_GAME_2 = 1002
IGDB_GAME_3 = 1003
IGDB_GAME_4 = 1004

MOCK_GAME_2 = {
    "id": IGDB_GAME_2,
    "name": "Game 2",
    "slug": "game-2",
    "cover": {"image_id": "co1abc"},
    "rating": 84.0,
}
MOCK_GAME_3 = {
    "id": IGDB_GAME_3,
    "name": "Game 3",
    "slug": "game-3",
    "cover": {"image_id": "co2def"},
    "rating": 78.0,
}


class SimilarGameAPITest(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()

        # game1과 유사 게임 관계 생성 (IGDB ID 기반)
        GameSimilarity.objects.create(igdb_game_id=IGDB_GAME_1, igdb_similar_game_id=IGDB_GAME_2, score=0.9)
        GameSimilarity.objects.create(igdb_game_id=IGDB_GAME_1, igdb_similar_game_id=IGDB_GAME_3, score=0.7)

    # limit=2 지정했을 때 유사 게임 200
    @patch("apps.games.services.similar_game.igdb_cache.get_games_by_ids")
    def test_similar_games_success_with_limit(self, mock_get_games: object) -> None:
        mock_get_games.return_value = [MOCK_GAME_2, MOCK_GAME_3]  # type: ignore[attr-defined]

        url = f"/api/v1/games/{IGDB_GAME_1}/similar/"
        response = self.client.get(url, {"limit": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        json_data = response.json()
        self.assertIn("results", json_data)

        results = json_data["results"]
        self.assertEqual(len(results), 2)

        # score 내림차순 확인
        self.assertGreaterEqual(results[0]["similarity_score"], results[1]["similarity_score"])

        # 각 필드 확인
        for item in results:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIn("slug", item)
            self.assertIn("thumbnail_img_url", item)
            self.assertIn("similarity_score", item)

    # limit 미지정 200
    @patch("apps.games.services.similar_game.igdb_cache.get_games_by_ids")
    def test_similar_games_default_limit(self, mock_get_games: object) -> None:
        mock_get_games.return_value = [MOCK_GAME_2, MOCK_GAME_3]  # type: ignore[attr-defined]

        url = f"/api/v1/games/{IGDB_GAME_1}/similar/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        # 실제 존재하는 유사 게임 2개 반환
        self.assertEqual(len(response.data["results"]), 2)

    # limit=1 지정 시 -> 1개만 나오는지
    @patch("apps.games.services.similar_game.igdb_cache.get_games_by_ids")
    def test_similar_games_limit_applied(self, mock_get_games: object) -> None:
        mock_get_games.return_value = [MOCK_GAME_2]  # type: ignore[attr-defined]

        url = f"/api/v1/games/{IGDB_GAME_1}/similar/"
        response = self.client.get(url, {"limit": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    # 유사게임 없을 시 -> 빈 배열 반환
    def test_similar_games_no_similar_games(self) -> None:
        url = f"/api/v1/games/{IGDB_GAME_4}/similar/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 0)

    # 비정상 limit 값 400
    def test_similar_games_invalid_limit(self) -> None:
        url = f"/api/v1/games/{IGDB_GAME_1}/similar/"
        response = self.client.get(url, {"limit": -3})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_QUERY_PARAM")
