from typing import Any

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.games.models import Platform


class PlatformListAPITest(APITestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()

        # 기존 데이터 정리 후 테스트 데이터 생성
        Platform.objects.all().delete()

        self.platform1 = Platform.objects.create(
            igdb_id=101,
            name="PC",
            slug="pc",
        )

        self.platform2 = Platform.objects.create(
            igdb_id=102,
            name="PlayStation 5",
            slug="playstation5",
        )

    # 전체 플랫폼 조회 정상
    def test_get_all_platforms_success(self) -> None:
        url = reverse("platform-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

        results: list[dict[str, Any]] = response.data["results"]
        self.assertEqual(len(results), 2)

        # 필드 존재 확인
        for item in results:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIn("slug", item)

        # 데이터 확인
        self.assertEqual(results[0]["id"], self.platform1.id)
        self.assertEqual(results[0]["name"], "PC")
        self.assertEqual(results[0]["slug"], "pc")

        self.assertEqual(results[1]["id"], self.platform2.id)
        self.assertEqual(results[1]["name"], "PlayStation 5")
        self.assertEqual(results[1]["slug"], "playstation5")

    # 플랫폼이 없을 때 빈 리스트 반환
    def test_get_all_platforms_empty(self) -> None:
        Platform.objects.all().delete()

        url = reverse("platform-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["results"], [])

    # 서비스가 항상 DB에서 조회하는지 확인
    def test_get_all_platforms_returns_db_data(self) -> None:
        url = reverse("platform-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results: list[dict[str, Any]] = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "PC")
