from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.games.models import Tag


class TagListAPITest(APITestCase):
    def setUp(self) -> None:
        self.url = reverse("tag-list")
        Tag.objects.all().delete()

        # 테스트 데이터
        Tag.objects.get_or_create(igdb_id=1, igdb_type="theme", slug="open-world", defaults={"name": "Open World"})
        Tag.objects.get_or_create(igdb_id=2, igdb_type="genre", slug="multiplayer", defaults={"name": "Multiplayer"})
        Tag.objects.get_or_create(igdb_id=3, igdb_type="theme", slug="rpg", defaults={"name": "Rpg"})

    def test_get_all_tags(self) -> None:
        """Service 실제 실행해서 전체 태그 조회"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 3)
