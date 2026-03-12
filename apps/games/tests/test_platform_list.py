from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.games.models import Platform


class PlatformListAPITest(APITestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()

        cache.clear()

        # 테스트 플랫폼 데이터 생성
        self.platform1 = Platform.objects.create(
            id=1,
            rawg_id=1,
            name="PC",
            slug="pc",
            icon_url=None,
        )

        self.platform2 = Platform.objects.create(
            id=2,
            rawg_id=2,
            name="PlayStation 5",
            slug="playstation5",
            icon_url="https://cdn.example.com/ps5.png",
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
            self.assertIn("icon_url", item)

        # 데이터 확인
        self.assertEqual(results[0]["id"], 1)
        self.assertEqual(results[0]["name"], "PC")
        self.assertEqual(results[0]["slug"], "pc")
        self.assertIsNone(results[0]["icon_url"])

        self.assertEqual(results[1]["id"], 2)
        self.assertEqual(results[1]["name"], "PlayStation 5")
        self.assertEqual(results[1]["slug"], "playstation5")
        self.assertEqual(results[1]["icon_url"], "https://cdn.example.com/ps5.png")

    # 플랫폼이 없을 때 빈 리스트 반환
    def test_get_all_platforms_empty(self) -> None:
        Platform.objects.all().delete()

        url = reverse("platform-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["results"], [])

    # 캐시에 값 있을 때 -> db 조회 x, 캐시 바로 반환
    def test_get_all_platforms_cache_hit(self) -> None:
        # self.client.get(url)보다 먼저 실행되어 setup의 db데이터는 캐시 저장 x
        cache.set(
            settings.PLATFORMS_CACHE_KEY,
            [
                {
                    "id": 3,
                    "name": "Nintendo Switch",
                    "slug": "nintendo-switch",
                    "icon_url": None,
                }
            ],
        )

        url = reverse("platform-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results: list[dict[str, Any]] = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Nintendo Switch")
