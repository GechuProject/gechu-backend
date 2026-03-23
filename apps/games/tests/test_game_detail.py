from datetime import date
from unittest.mock import patch

from rest_framework.test import APIClient

from apps.core.testcase import FastTestCase
from apps.games.igdb.exceptions import IgdbNotFoundError
from apps.users.models import User

# Sample IGDB game detail response (matches build_game_detail output shape)
MOCK_GAME_DETAIL = {
    "id": 1942,
    "slug": "the-witcher-3",
    "name": "The Witcher 3",
    "description": "An epic RPG",
    "released": "2015-05-19",
    "tba": False,
    "thumbnail_img_url": "https://images.igdb.com/igdb/image/upload/t_cover_big/co1wyy.jpg",
    "website": "https://thewitcher.com",
    "rawg_rating": 4.66,
    "rawg_ratings_count": 6000,
    "rawg_added": 120000,
    "esrb_rating": "mature",
    "age_rating_min": 17,
    "genres": [{"id": 12, "name": "RPG", "slug": "rpg"}],
    "platforms": [{"id": 6, "name": "PC"}],
    "tags": [{"id": 321, "name": "Open World"}],
    "media": [],
    "stores": [],
}

MOCK_ADULT_GAME_DETAIL = {
    **MOCK_GAME_DETAIL,
    "id": 9999,
    "esrb_rating": "adults-only",
    "age_rating_min": 18,
}


class GameDetailAPITest(FastTestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()

    @patch("apps.games.services.game_detail.igdb_cache.get_game_detail")
    def test_game_detail_success(self, mock_get_detail: object) -> None:
        """게임 상세 조회 성공"""
        mock_get_detail.return_value = MOCK_GAME_DETAIL  # type: ignore[attr-defined]

        url = "/api/v1/games/1942/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["id"], 1942)
        self.assertEqual(data["name"], "The Witcher 3")
        self.assertEqual(data["slug"], "the-witcher-3")
        self.assertEqual(len(data["genres"]), 1)
        self.assertEqual(data["genres"][0]["name"], "RPG")
        self.assertEqual(len(data["platforms"]), 1)
        self.assertEqual(data["platforms"][0]["name"], "PC")
        self.assertEqual(len(data["tags"]), 1)
        self.assertEqual(data["tags"][0]["name"], "Open World")

    @patch("apps.games.services.game_detail.igdb_cache.get_game_detail")
    def test_game_detail_not_found(self, mock_get_detail: object) -> None:
        """존재하지 않는 게임"""
        mock_get_detail.side_effect = IgdbNotFoundError("Game not found: igdb_id=9999")  # type: ignore[attr-defined]

        url = "/api/v1/games/9999/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

        data = response.json()

        self.assertEqual(data["code"], "GAME_NOT_FOUND")

    @patch("apps.games.services.game_detail.igdb_cache.get_game_detail")
    def test_adult_game_requires_verification(self, mock_get_detail: object) -> None:
        """성인 게임 + 인증 안된 유저"""
        mock_get_detail.return_value = MOCK_ADULT_GAME_DETAIL  # type: ignore[attr-defined]

        url = "/api/v1/games/9999/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

        data = response.json()

        self.assertEqual(data["code"], "ADULT_VERIFICATION_REQUIRED")

    @patch("apps.games.services.game_detail.igdb_cache.get_game_detail")
    def test_adult_game_verified_user(self, mock_get_detail: object) -> None:
        """성인 인증 유저 접근"""
        mock_get_detail.return_value = MOCK_ADULT_GAME_DETAIL  # type: ignore[attr-defined]

        user = User.objects.create_user(
            email="adult@test.com",
            nickname="adult_user",
            birth_date=date(1990, 1, 1),
            password="password",
            is_adult_verified=True,
        )

        self.client.force_authenticate(user=user)

        url = "/api/v1/games/9999/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
