from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.exceptions.exception_message import ErrorMessages

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
    def test_search_filter(self, mock_search: object) -> None:
        """검색어 필터 적용"""
        mock_search.return_value = [MOCK_GAME_LIST_ITEM]  # type: ignore[attr-defined]

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"search": "Test"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        # Second search returns empty
        mock_search.return_value = []  # type: ignore[attr-defined]
        response = self.client.get(self.url, {"search": "NoMatch"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)
