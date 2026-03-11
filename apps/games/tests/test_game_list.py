from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models.catalog import Game
from apps.games.models.metadata import Genre, Platform, Tag

User = get_user_model()


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

        # 장르, 플랫폼, 태그
        self.genre = Genre.objects.create(name="Action", rawg_id=1)
        self.platform = Platform.objects.create(name="PC", rawg_id=1)
        self.tag = Tag.objects.create(name="Multiplayer", rawg_id=1)

        # 게임 생성
        self.game = Game.objects.create(
            name="Test Game",
            slug="test-game",
            released="2025-01-01",
            thumbnail_img_url="http://example.com/thumb.jpg",
            rawg_id=1,
            rawg_rating=4.5,
            rawg_ratings_count=100,
            metacritic=90,
            esrb_rating="everyone",
            age_rating_min=0,
            is_visible=True,
        )
        self.game.game_genres.create(genre=self.genre)
        self.game.game_platforms.create(platform=self.platform)
        self.game.game_tags.create(tag=self.tag)

        self.url = reverse("game-list")

    def test_game_list_success(self) -> None:
        """정상 요청 - 기본 쿼리"""
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

    def test_search_filter(self) -> None:
        """검색어 필터 적용"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"search": "Test"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get(self.url, {"search": "NoMatch"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_esrb_rating_filter(self) -> None:
        """ESRB 필터 적용"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"esrb_rating": "everyone"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        response = self.client.get(self.url, {"esrb_rating": "mature"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_adult_filter(self) -> None:
        """성인 미인증 필터"""
        self.client.force_authenticate(user=self.user)
        self.user.is_adult_verified = False
        self.user.save()

        # age_rating_min 0인 게임은 포함
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        # age_rating_min 18 이상인 게임 추가
        _ = Game.objects.create(
            name="Adult Game",
            slug="adult-game",
            released="2025-01-01",
            thumbnail_img_url="http://example.com/adult.jpg",
            rawg_id=2,
            rawg_rating=5.0,
            rawg_ratings_count=50,
            metacritic=95,
            esrb_rating=Game.EsrbRating.ADULTS_ONLY,
            is_visible=True,
        )
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 1)  # 성인인증 x라 생성한 성인게임은 포함되지 않아 1임
