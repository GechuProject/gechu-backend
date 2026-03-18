from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.services.game_list import GameService

User = get_user_model()

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
    "tags": [{"id": 100, "name": "SinglePlayer"}],
    "esrb_rating": "everyone",
    "age_rating_min": 0,
}

MOCK_GAME_LIST_ITEM_2 = {
    "id": 1943,
    "slug": "test-game-2",
    "name": "Test Game 2",
    "released": "2025-01-01",
    "thumbnail_img_url": "https://images.igdb.com/igdb/image/upload/t_cover_big/co2wyy.jpg",
    "rawg_rating": 4.8,
    "rawg_ratings_count": 50,
    "genres": [{"id": 13, "name": "FPS"}],
    "platforms": [{"id": 7, "name": "Xbox"}],
    "tags": [{"id": 101, "name": "Multiplayer"}],
    "esrb_rating": "everyone",
    "age_rating_min": 0,
}


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
        self.user = User.objects.create_user(
            email="test@example.com",
            password="password123",
            nickname="TestUser",
            birth_date=date(1997, 1, 1),
            is_adult_verified=True,
        )
        self.url = reverse("game-list")
        self.connection = get_redis_connection("default")

    def _recent_search_key(self, *, user_id: int) -> str:
        return f"search:recent:{user_id}"

    def _get_recent_keywords(self) -> list[str]:
        raw_keywords = self.connection.lrange(self._recent_search_key(user_id=self.user.id), 0, -1)
        return [keyword.decode("utf-8") if isinstance(keyword, bytes) else str(keyword) for keyword in raw_keywords]

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    def test_genre_platform_tag_filtering(self, mock_search: MagicMock) -> None:
        """
        genre_ids, platform_ids, tag_ids 후처리 필터링 테스트
        """
        mock_search.return_value = [MOCK_GAME_LIST_ITEM, MOCK_GAME_LIST_ITEM_2]

        self.client.force_authenticate(user=self.user)

        # genre_ids 필터링: 12번 장르만 통과
        response = self.client.get(self.url, {"genre_ids": "12"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["genres"][0]["id"], 12)

        # platform_ids 필터링: 6번 플랫폼만 통과
        response = self.client.get(self.url, {"platform_ids": "6"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["platforms"][0]["id"], 6)

        # tag_ids 필터링: 101번 태그만 통과
        response = self.client.get(self.url, {"tag_ids": "101"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["tags"][0]["id"], 101)

        # 복합 필터링: genre 12, platform 6, tag 100
        response = self.client.get(self.url, {"genre_ids": "12", "platform_ids": "6", "tag_ids": "100"})
        self.assertEqual(len(response.data["results"]), 1)
        game = response.data["results"][0]
        self.assertEqual(game["genres"][0]["id"], 12)
        self.assertEqual(game["platforms"][0]["id"], 6)
        self.assertEqual(game["tags"][0]["id"], 100)

        # 아무 것도 통과하지 못하는 경우.
        response = self.client.get(self.url, {"genre_ids": "999"})
        self.assertEqual(len(response.data["results"]), 0)

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    def test_pagination_slicing(self, mock_search: MagicMock) -> None:
        """
        page_size 적용 후처리 테스트
        """
        mock_search.return_value = [MOCK_GAME_LIST_ITEM] * 5
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"page_size": 3})
        self.assertEqual(len(response.data["results"]), 3)

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    def test_game_list_success(self, mock_search: object) -> None:
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
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"ordering": "invalid_field"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], ErrorMessages.INVALID_ORDERING.name)
        self.assertEqual(response.data["message"], ErrorMessages.INVALID_ORDERING.message)

    def test_invalid_genre_ids(self) -> None:
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"genre_ids": "abc,123"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], ErrorMessages.INVALID_QUERY_PARAM.name)
        self.assertEqual(response.data["message"], ErrorMessages.INVALID_QUERY_PARAM.message)

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    def test_search_and_ordering(self, mock_search: MagicMock) -> None:
        self.client.force_authenticate(user=self.user)

        mock_search.return_value = [MOCK_GAME_LIST_ITEM]
        response = self.client.get(
            self.url,
            {"search": "Test", "ordering": "-rawg_rating"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        game_data = response.data["results"][0]
        self.assertEqual(game_data["name"], "Test Game")

        mock_search.return_value = []
        response = self.client.get(self.url, {"search": "NoMatch"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    def test_search_saves_recent_keyword(self, mock_search: object) -> None:
        self.client.force_authenticate(user=self.user)
        self.connection.delete(self._recent_search_key(user_id=self.user.id))

        mock_search.return_value = [MOCK_GAME_LIST_ITEM]  # type: ignore[attr-defined]
        first_response = self.client.get(self.url, {"search": "Test"})
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._get_recent_keywords(), ["Test"])

        mock_search.return_value = []  # type: ignore[attr-defined]
        second_response = self.client.get(self.url, {"search": "NoMatch"})
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._get_recent_keywords(), ["NoMatch", "Test"])

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    @patch("apps.games.services.game_list.igdb_cache.get_genre_id_by_name")
    def test_top_n_by_genre_service_real(self, mock_get_genre_id: MagicMock, mock_search: MagicMock) -> None:
        mock_get_genre_id.return_value = 12
        mock_search.return_value = MOCK_TOP10_GAMES

        result = GameService.top_n_by_genre("Action")

        self.assertEqual(len(result), 10)
        self.assertEqual(result[0]["rawg_rating"], 5.5)
        self.assertAlmostEqual(result[-1]["rawg_rating"], 4.6)

        mock_get_genre_id.return_value = None

        result = GameService.top_n_by_genre("NonExistent")

        self.assertEqual(result, [])

    @patch("apps.games.services.game_list.GameService.top_n_by_genre")
    def test_top_n_by_genre_api_mocked(self, mock_top_n: MagicMock) -> None:
        mock_top_n.return_value = MOCK_TOP10_GAMES
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url, {"genre_name": "Action"})
        self.assertEqual(len(resp.data["results"]), 10)
        self.assertEqual(resp.data["results"][0]["rawg_rating"], "5.50")
        self.assertIsNone(resp.data["next"])
        self.assertIsNone(resp.data["previous"])

        mock_top_n.return_value = []
        resp = self.client.get(self.url, {"genre_name": "NonExistent"})
        self.assertEqual(resp.data["results"], [])
