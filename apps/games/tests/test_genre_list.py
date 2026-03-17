from typing import Any

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.games.models import Genre


class GenreListAPITest(APITestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()

        # 기존 데이터 정리 후 테스트 데이터 생성
        Genre.objects.all().delete()

        self.genre1 = Genre.objects.create(igdb_id=101, igdb_type=Genre.IgdbType.GENRE, name="Action", slug="action")
        self.genre2 = Genre.objects.create(
            igdb_id=102, igdb_type=Genre.IgdbType.GENRE, name="RPG", slug="role-playing-games-rpg"
        )

    # 전체 장르 조회 정상
    def test_get_all_genres_success(self) -> None:
        url = reverse("genre-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

        results: list[dict[str, Any]] = response.data["results"]
        self.assertEqual(len(results), 2)

        # 각 필드 확인
        for item in results:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIn("slug", item)

        # 데이터 순서 및 값 확인
        self.assertEqual(results[0]["id"], self.genre1.id)
        self.assertEqual(results[0]["name"], "Action")
        self.assertEqual(results[0]["slug"], "action")
        self.assertEqual(results[1]["id"], self.genre2.id)
        self.assertEqual(results[1]["name"], "RPG")
        self.assertEqual(results[1]["slug"], "role-playing-games-rpg")

    # 장르가 없을 때 빈 리스트 반환
    def test_get_all_genres_empty(self) -> None:
        # DB 초기화
        Genre.objects.all().delete()

        url = reverse("genre-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["results"], [])

    # 서비스가 항상 DB에서 조회하는지 확인
    def test_get_all_genres_returns_db_data(self) -> None:
        url = reverse("genre-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
