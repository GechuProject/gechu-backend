from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from apps.games.models import (
    ExternalStore,
    Game,
    GameGenre,
    GameMedia,
    GamePlatform,
    GameStore,
    GameTag,
    Genre,
    Platform,
    Tag,
)
from apps.users.models import User


class GameDetailAPITest(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()

        # 테스트용 게임 생성
        self.game = Game.objects.create(
            rawg_id=1,
            slug="the-witcher-3",
            name="The Witcher 3",
            description="An epic RPG",
            thumbnail_img_url="https://cdn.example.com/img/w3.jpg",
            website="https://thewitcher.com",
            rawg_rating=4.66,
            rawg_ratings_count=6000,
            metacritic=92,
            rawg_added=120000,
            playtime=46,
            esrb_rating="mature",
            age_rating_min=17,
            is_visible=True,
        )

        genre = Genre.objects.create(rawg_id=1, name="RPG", slug="rpg")
        GameGenre.objects.create(game=self.game, genre=genre)

        platform = Platform.objects.create(rawg_id=1, name="PC", slug="pc")
        GamePlatform.objects.create(
            game=self.game, platform=platform, requirements_minimum="min", requirements_recommended="rec"
        )

        tag = Tag.objects.create(rawg_id=1, name="Open World", slug="open-world")
        GameTag.objects.create(game=self.game, tag=tag)

        GameMedia.objects.create(game=self.game, rawg_id=1, type="screenshot", media_url="img.jpg")

        store = ExternalStore.objects.create(rawg_id=1, name="Steam", slug="steam", domain="store.steampowered.com")

        GameStore.objects.create(game=self.game, store=store, url="https://store.steampowered.com/app/1")

    def test_game_detail_success(self) -> None:
        """게임 상세 조회 성공"""

        url = f"/api/v1/games/{self.game.id}/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["id"], self.game.id)
        self.assertEqual(data["name"], "The Witcher 3")
        self.assertEqual(data["slug"], "the-witcher-3")
        self.assertEqual(len(data["genres"]), 1)
        self.assertEqual(data["genres"][0]["name"], "RPG")
        self.assertEqual(len(data["platforms"]), 1)
        self.assertEqual(data["platforms"][0]["name"], "PC")
        self.assertEqual(len(data["tags"]), 1)
        self.assertEqual(data["tags"][0]["name"], "Open World")

    def test_game_detail_not_found(self) -> None:
        """존재하지 않는 게임"""

        url = "/api/v1/games/9999/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

        data = response.json()

        self.assertEqual(data["code"], "GAME_NOT_FOUND")

    def test_game_not_visible(self) -> None:
        """is_visible=False 게임"""

        self.game.is_visible = False
        self.game.save()

        url = f"/api/v1/games/{self.game.id}/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_adult_game_requires_verification(self) -> None:
        """성인 게임 + 인증 안된 유저"""

        self.game.esrb_rating = Game.EsrbRating.ADULTS_ONLY
        self.game.save()

        url = f"/api/v1/games/{self.game.id}/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

        data = response.json()

        self.assertEqual(data["code"], "ADULT_VERIFICATION_REQUIRED")

    def test_adult_game_verified_user(self) -> None:
        """성인 인증 유저 접근"""

        user = User.objects.create_user(
            email="adult@test.com",
            nickname="adult_user",
            birth_date=date(1990, 1, 1),
            password="password",
            is_adult_verified=True,
        )

        self.client.force_authenticate(user=user)

        self.game.esrb_rating = Game.EsrbRating.ADULTS_ONLY
        self.game.save()

        url = f"/api/v1/games/{self.game.id}/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
