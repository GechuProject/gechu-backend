from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models import Genre
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
    "is_saved": False,
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
        "is_saved": False,
    }
    for i in range(1, 11)
]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
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

        # 테스트용 장르 생성
        self.rpg_genre, _ = Genre.objects.get_or_create(
            igdb_id=12,
            igdb_type="genre",
            defaults={"name": "RPG"},
        )

    def _recent_search_key(self, *, user_id: int) -> str:
        return f"search:recent:{user_id}"

    def _get_recent_keywords(self) -> list[str]:
        raw_keywords = self.connection.lrange(self._recent_search_key(user_id=self.user.id), 0, -1)
        return [keyword.decode("utf-8") if isinstance(keyword, bytes) else str(keyword) for keyword in raw_keywords]

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
    def test_game_list_success(self, mock_search: MagicMock) -> None:
        mock_search.return_value = [MOCK_GAME_LIST_ITEM]

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

    def test_invalid_ids_not_in_db(self) -> None:
        self.client.force_authenticate(user=self.user)

        test_cases = {
            "genre_ids": ErrorMessages.INVALID_GENRE_ID,
            "platform_ids": ErrorMessages.INVALID_PLATFORM_ID,
            "tag_ids": ErrorMessages.INVALID_TAG_ID,
        }

        for param, error_message in test_cases.items():
            with self.subTest(param=param):
                response = self.client.get(self.url, {param: "999"})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data["code"], error_message.name)
                self.assertEqual(response.data["message"], error_message.message)

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

    def test_top_n_by_genre_service_real(self) -> None:
        with patch("apps.games.services.game_list.igdb_cache.search_games_by_igdb_genre_id") as mock_search:
            mock_search.return_value = MOCK_TOP10_GAMES
            result = GameService.top_n_by_genre("RPG")

        self.assertEqual(len(result), 10)
        self.assertEqual(result[0]["rawg_rating"], 5.5)
        self.assertAlmostEqual(result[-1]["rawg_rating"], 4.6)

        result = GameService.top_n_by_genre("NonExistent")
        self.assertEqual(result, [])

    def test_genre_name_returns_top_n(self) -> None:

        with patch("apps.games.services.game_list.igdb_cache.search_games_by_igdb_genre_id") as mock_search:
            mock_search.return_value = MOCK_TOP10_GAMES

            self.client.force_authenticate(user=self.user)
            response = self.client.get(self.url, {"genre_name": "RPG"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNone(response.data["next"])
        self.assertIsNone(response.data["previous"])

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    def test_pagination_next_url(self, mock_search: MagicMock) -> None:
        """has_next=True일 때 next_url 생성"""
        # page_size=2 요청 시 3개 반환 → has_next=True
        mock_search.return_value = [MOCK_GAME_LIST_ITEM] * 3

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"page": 1, "page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])
        self.assertIn("page=2", response.data["next"])

    @patch("apps.games.services.game_list.igdb_cache.search_games")
    def test_pagination_previous_url(self, mock_search: MagicMock) -> None:
        """page > 1일 때 previous_url 생성"""
        mock_search.return_value = [MOCK_GAME_LIST_ITEM]

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"page": 2, "page_size": 20})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["previous"])
        self.assertIn("page=1", response.data["previous"])
