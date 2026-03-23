from __future__ import annotations

import datetime

from django.contrib.auth import get_user_model
from django_redis import get_redis_connection
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase


class RecentSearchAPITest(FastTestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="recent@example.com",
            password="Passw0rd!",
            nickname="recent-user",
            birth_date=datetime.date(1999, 1, 1),
        )
        self.key = f"search:recent:{self.user.id}"
        self.connection = get_redis_connection("default")
        self.connection.delete(self.key)

    def tearDown(self) -> None:
        self.connection.delete(self.key)

    def test_get_recent_searches_returns_latest_keywords(self) -> None:
        self.connection.lpush(self.key, "elden ring")
        self.connection.lpush(self.key, "cyberpunk")
        self.connection.lpush(self.key, "witcher")
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/search/recent/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": ["witcher", "cyberpunk", "elden ring"]})

    def test_get_recent_searches_returns_401_when_not_authenticated(self) -> None:
        response = self.client.get("/api/v1/search/recent/")

        self.assertEqual(response.status_code, 401)

    def test_delete_recent_searches_clears_all_keywords(self) -> None:
        self.connection.rpush(self.key, "witcher", "cyberpunk")
        self.client.force_authenticate(user=self.user)

        response = self.client.delete("/api/v1/search/recent/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "최근 검색어가 모두 삭제되었습니다."})
        self.assertEqual(self.connection.lrange(self.key, 0, -1), [])

    def test_delete_recent_searches_returns_401_when_not_authenticated(self) -> None:
        response = self.client.delete("/api/v1/search/recent/")

        self.assertEqual(response.status_code, 401)

    def test_delete_recent_search_keyword_removes_matching_keyword(self) -> None:
        self.connection.rpush(self.key, "witcher", "cyberpunk", "elden ring")
        self.client.force_authenticate(user=self.user)

        response = self.client.delete("/api/v1/search/recent/cyberpunk/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "검색어가 삭제되었습니다."})
        self.assertEqual(self.connection.lrange(self.key, 0, -1), [b"witcher", b"elden ring"])

    def test_delete_recent_search_keyword_returns_401_when_not_authenticated(self) -> None:
        response = self.client.delete("/api/v1/search/recent/cyberpunk/")

        self.assertEqual(response.status_code, 401)

    def test_delete_recent_search_keyword_returns_404_when_keyword_not_found(self) -> None:
        self.connection.rpush(self.key, "witcher")
        self.client.force_authenticate(user=self.user)

        response = self.client.delete("/api/v1/search/recent/cyberpunk/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], ErrorMessages.SEARCH_KEYWORD_NOT_FOUND.name)

    def test_delete_recent_search_keyword_allows_slash_in_keyword(self) -> None:
        self.connection.rpush(self.key, "Nier/Automata")
        self.client.force_authenticate(user=self.user)

        response = self.client.delete("/api/v1/search/recent/Nier/Automata/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "검색어가 삭제되었습니다."})
        self.assertEqual(self.connection.lrange(self.key, 0, -1), [])
