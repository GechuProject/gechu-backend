from typing import Any

from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.games.models import Genre


class GenreListAPITest(APITestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()

        # 테스트마다 매번 캐시 초기화
        cache.clear()

        # 테스트용 장르 데이터 생성
        self.genre1 = Genre.objects.create(id=1, rawg_id=1, name="Action", slug="action")
        self.genre2 = Genre.objects.create(id=2, rawg_id=2, name="RPG", slug="role-playing-games-rpg")

    # 전체 장르 조회 정상
    def test_get_all_genres_success(self) -> None:
        url = "/api/v1/games/genres/"
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
        self.assertEqual(results[0]["id"], 1)
        self.assertEqual(results[0]["name"], "Action")
        self.assertEqual(results[0]["slug"], "action")
        self.assertEqual(results[1]["id"], 2)
        self.assertEqual(results[1]["name"], "RPG")
        self.assertEqual(results[1]["slug"], "role-playing-games-rpg")

    # 장르가 없을 때 빈 리스트 반환
    def test_get_all_genres_empty(self) -> None:
        # DB 초기화
        Genre.objects.all().delete()

        url = "/api/v1/games/genres/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["results"], [])

    # 캐시에 값 있을 때 -> db 조회 x, 캐시 바로 반환
    def test_get_all_genres_cache_hit(self) -> None:
        # self.client.get(url)보다 먼저 실행되어 setup의 db데이터는 캐시 저장 x
        cache.set(
            "genres:all",
            [{"id": 3, "name": "Indie", "slug": "indie"}],
        )

        url = "/api/v1/games/genres/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
