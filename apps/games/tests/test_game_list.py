from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.services.game_list import GameService

User = get_user_model()

# Sample IGDB search result items (matches build_game_list_item output shape)
MOCK_GAME_LIST_ITEM = {
    "id": 1942,
    "slug": "test-game",
    "name": "Test Game",
    "released": "2025-01-01",
    "thumbnail_img_url": "https://images.igdb.com/igdb/image/upload/t_cover_big/co1wyy.jpg",
    "rawg_rating": 4.50,
    "rawg_ratings_count": 100,
    "genres": [{"id": 12, "name": "Action"}],
    "platforms": [{"id": 6, "name": "PC"}],
    "esrb_rating": "everyone",
    "age_rating_min": 0,
}

# Mock Top 10 games for genre_name test
MOCK_TOP10_GAMES = [
    {
        "id": i,
        "slug": f"test-game-{i}",
        "name": f"Test Game {i}",
        "released": "2025-01-01",
        "thumbnail_img_url": f"https://images.igdb.com/igdb/image/upload/t_cover_big/co{i}wyy.jpg",
        "rawg_rating": 5.5 - (i - 1) * 0.1,
        "rawg_ratings_count": 100 + i * 10,
        "genres": [{"id": 12, "name": "Action"}, {"id": 13, "name": "FPS"}],
        "platforms": [{"id": 6, "name": "PC"}],
        "esrb_rating": "everyone",
        "age_rating_min": 0,
    }
    for i in range(1, 11)
]


class GameListViewTests(APITestCase):
    def setUp(self) -> None:
        # 테스트 유저
        self.user = User.objects.create_user(
            email="test@example.com",
            password="password123",
            nickname="TestUser",
            birth_date=date(1997, 1, 1),
            is_adult_verified=True,
        )

        self.url = reverse("game-list")

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    def test_game_list_success(self, mock_search: object) -> None:
        """정상 요청 - 기본 쿼리"""
        mock_search.return_value = [MOCK_GAME_LIST_ITEM]  # type: ignore[attr-defined]

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        game_data = response.data["results"][0]
        self.assertEqual(game_data["name"], "Test Game")
        self.assertEqual(game_data["genres"][0]["name"], "Action")

    def test_invalid_ordering(self) -> None:
        """잘못된 ordering 값"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"ordering": "invalid_field"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], ErrorMessages.INVALID_ORDERING.name)
        self.assertEqual(response.data["message"], ErrorMessages.INVALID_ORDERING.message)

    def test_invalid_genre_ids(self) -> None:
        """잘못된 genre_ids 값"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"genre_ids": "abc,123"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], ErrorMessages.INVALID_QUERY_PARAM.name)
        self.assertEqual(response.data["message"], ErrorMessages.INVALID_QUERY_PARAM.message)

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    def test_search_and_ordering(self, mock_search: MagicMock) -> None:
        """검색 + 정렬 통합 테스트"""
        self.client.force_authenticate(user=self.user)

        # 검색 결과 있음
        mock_search.return_value = [MOCK_GAME_LIST_ITEM]

        response = self.client.get(
            self.url,
            {"search": "Test", "ordering": "-rawg_rating"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        game_data = response.data["results"][0]
        self.assertEqual(game_data["name"], "Test Game")

        # 검색 결과 없음
        mock_search.return_value = []

        response = self.client.get(self.url, {"search": "NoMatch"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    @patch("apps.games.services.game_list.igdb_cache.get_genre_id_by_name")
    def test_top_n_by_genre_service_real(self, mock_get_genre_id: MagicMock, mock_search: MagicMock) -> None:
        """top_n_by_genre 내부 분기와 검색까지 실제 실행"""
        # ------------------
        # 장르 존재
        # ------------------
        mock_get_genre_id.return_value = 12
        mock_search.return_value = MOCK_TOP10_GAMES

        result = GameService.top_n_by_genre("Action")

        self.assertEqual(len(result), 10)
        self.assertEqual(result[0]["rawg_rating"], 5.5)
        self.assertAlmostEqual(result[-1]["rawg_rating"], 4.6)

        # ------------------
        # 장르 없음
        # ------------------
        mock_get_genre_id.return_value = None

        result = GameService.top_n_by_genre("NonExistent")

        self.assertEqual(result, [])

    @patch("apps.games.services.game_list.GameService.top_n_by_genre")
    def test_top_n_by_genre_api_mocked(self, mock_top_n: MagicMock) -> None:
        """API 레이어 테스트: top_n_by_genre patch"""
        mock_top_n.return_value = MOCK_TOP10_GAMES
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url, {"genre_name": "Action"})
        self.assertEqual(len(resp.data["results"]), 10)
        self.assertEqual(resp.data["results"][0]["rawg_rating"], "5.50")
        self.assertIsNone(resp.data["next"])
        self.assertIsNone(resp.data["previous"])

        # 빈 리스트 반환
        mock_top_n.return_value = []
        resp = self.client.get(self.url, {"genre_name": "NonExistent"})
        self.assertEqual(resp.data["results"], [])
