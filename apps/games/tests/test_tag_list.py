from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.games.models import Tag


class TagListAPITest(APITestCase):
    def setUp(self) -> None:
        self.url = reverse("tag-list")

        # 테스트 데이터
        Tag.objects.create(rawg_id=1, name="Open World", slug="open-world")
        Tag.objects.create(rawg_id=2, name="Multiplayer", slug="multiplayer")
        Tag.objects.create(rawg_id=3, name="RPG", slug="rpg")

    # 전체 태그 목록 조회 (200)
    def test_get_all_tags(self) -> None:
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)

        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 3)

    # 검색 200
    def test_search_filter(self) -> None:
        response = self.client.get(self.url, {"search": "open"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Open World")

    # slug 기준 검색 200
    def test_search_slug_filter(self) -> None:
        response = self.client.get(self.url, {"search": "multi"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "multiplayer")

    # 페이지네이션 200
    def test_pagination(self) -> None:
        response = self.client.get(self.url, {"page": 1, "page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)

    # 2페이지 조회 200
    def test_second_page(self) -> None:
        """2페이지 조회"""
        response = self.client.get(self.url, {"page": 2, "page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 1)

    # 검색 결과 없음 200
    def test_empty_result(self) -> None:
        response = self.client.get(self.url, {"search": "zzz"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)
