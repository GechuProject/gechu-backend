from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models import Game
from apps.recommendations.models import GameSimilarity


class SimilarGameAPITest(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()

        # 테스트용 게임 3개 생성
        self.game1 = Game.objects.create(
            rawg_id=1,
            name="Game 1",
            slug="game-1",
            thumbnail_img_url="https://example.com/game1.jpg",
            rawg_rating=4.5,
        )
        self.game2 = Game.objects.create(
            rawg_id=2,
            name="Game 2",
            slug="game-2",
            thumbnail_img_url="https://example.com/game2.jpg",
            rawg_rating=4.2,
        )
        self.game3 = Game.objects.create(
            rawg_id=3,
            name="Game 3",
            slug="game-3",
            thumbnail_img_url="https://example.com/game3.jpg",
            rawg_rating=3.9,
        )

        # game1과 유사 게임 관계 생성
        GameSimilarity.objects.create(game=self.game1, similar_game=self.game2, score=0.9)
        GameSimilarity.objects.create(game=self.game1, similar_game=self.game3, score=0.7)

    # limit=2 지정했을 때 유사 게임 200
    def test_similar_games_success_with_limit(self) -> None:
        url = f"/api/v1/games/{self.game1.id}/similar/"
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
            self.assertIn("rawg_rating", item)
            self.assertIn("similarity_score", item)

    # limit 미지정 200
    def test_similar_games_default_limit(self) -> None:
        url = f"/api/v1/games/{self.game1.id}/similar/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        # 실제 존재하는 유사 게임 2개 반환
        self.assertEqual(len(response.data["results"]), 2)

    # 잘못된 게임 아이디
    def test_similar_games_invalid_game_id(self) -> None:
        url = "/api/v1/games/999999/similar/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], ErrorMessages.GAME_NOT_FOUND.name)
        self.assertEqual(response.data["message"], ErrorMessages.GAME_NOT_FOUND.message)

    # 비정상 limit 값 -> 기본값 10 처리 (view에서)
    def test_similar_games_invalid_limit(self) -> None:
        url = f"/api/v1/games/{self.game1.id}/similar/"
        response = self.client.get(url, {"limit": "not-an-int"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)
