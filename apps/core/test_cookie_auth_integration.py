from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from rest_framework.test import APIClient

from apps.core.auth_test_utils import authenticate_client_with_cookies, make_cookie_client
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.games.models import ExternalStore, Genre, Platform, Tag
from apps.interactions.models import InteractionContextRule, InteractionLog, InteractionWeightRule
from apps.recommendations.models import RecommendationJob
from apps.users.models import User


class CookieAuthPreferenceIntegrationTest(FastTestCase):
    def setUp(self) -> None:
        self.client: APIClient = make_cookie_client()
        self.user = User.objects.create_user(
            email="cookie-pref@example.com",
            password="Passw0rd!",
            nickname="cookie-pref",
            birth_date=date(1995, 1, 1),
        )
        authenticate_client_with_cookies(self.client, self.user)

    def test_preferences_put_succeeds_with_cookie_auth_and_csrf(self) -> None:
        genre = Genre.objects.create(igdb_id=1101, name="Cookie Action", slug="cookie-action")
        platform = Platform.objects.create(igdb_id=1201, name="Cookie PC", slug="cookie-pc")
        tag = Tag.objects.create(igdb_id=1301, name="Cookie Co-op", slug="cookie-co-op")

        response = self.client.put(
            "/api/v1/preferences/me/",
            {"genre_ids": [genre.id], "platform_ids": [platform.id], "tag_ids": [tag.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["genres"][0]["id"], genre.id)
        self.assertEqual(response.data["platforms"][0]["id"], platform.id)
        self.assertEqual(response.data["tags"][0]["id"], tag.id)

    def test_preferences_put_returns_403_without_csrf_header(self) -> None:
        self.client.credentials()

        response = self.client.put(
            "/api/v1/preferences/me/",
            {"genre_ids": [], "platform_ids": [], "tag_ids": []},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], ErrorMessages.CSRF_FAILED.name)


class CookieAuthInteractionIntegrationTest(FastTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        InteractionWeightRule.objects.bulk_create(
            [
                InteractionWeightRule(
                    interaction_type=InteractionWeightRule.ActionType.VIEW,
                    base_weight=Decimal("0.20"),
                    cooldown_seconds=0,
                    repeat_decay=Decimal("1.000"),
                    is_active=True,
                ),
                InteractionWeightRule(
                    interaction_type=InteractionWeightRule.ActionType.SEARCH,
                    base_weight=Decimal("0.10"),
                    cooldown_seconds=0,
                    repeat_decay=Decimal("1.000"),
                    is_active=True,
                ),
                InteractionWeightRule(
                    interaction_type=InteractionWeightRule.ActionType.STORE_CLICK,
                    base_weight=Decimal("0.30"),
                    cooldown_seconds=0,
                    repeat_decay=Decimal("1.000"),
                    is_active=True,
                ),
            ]
        )
        InteractionContextRule.objects.bulk_create(
            [
                InteractionContextRule(
                    interaction_source=InteractionContextRule.InteractionSource.RECOMMENDATION,
                    multiplier=Decimal("1.40"),
                ),
                InteractionContextRule(
                    interaction_source=InteractionContextRule.InteractionSource.SEARCH_RESULT,
                    multiplier=Decimal("1.10"),
                ),
                InteractionContextRule(
                    interaction_source=InteractionContextRule.InteractionSource.DETAIL_PAGE,
                    multiplier=Decimal("1.20"),
                ),
            ]
        )

    def setUp(self) -> None:
        self.client: APIClient = make_cookie_client()
        self.user = User.objects.create_user(
            email="cookie-interaction@example.com",
            password="Passw0rd!",
            nickname="cookie-interaction",
            birth_date=date(1994, 1, 1),
        )
        self.store = ExternalStore.objects.create(
            rawg_id=77,
            name="Steam",
            slug="steam",
            domain="store.steampowered.com",
        )
        authenticate_client_with_cookies(self.client, self.user)

    def test_interaction_view_succeeds_with_cookie_auth_and_csrf(self) -> None:
        response = self.client.post(
            "/api/v1/interactions/view/",
            {"game_id": 5001, "source": "recommendation", "metadata": {"slot": 1}},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["type"], InteractionLog.ActionType.VIEW)

    def test_interaction_search_succeeds_with_cookie_auth_and_csrf(self) -> None:
        response = self.client.post(
            "/api/v1/interactions/search/",
            {"game_id": 5002, "search_query": "elden ring", "source": "search_result"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["type"], InteractionLog.ActionType.SEARCH)

    def test_interaction_store_click_succeeds_with_cookie_auth_and_csrf(self) -> None:
        response = self.client.post(
            "/api/v1/interactions/store-click/",
            {"game_id": 5003, "store_id": self.store.id, "source": "detail_page"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["type"], InteractionLog.ActionType.STORE_CLICK)

    def test_interaction_view_returns_403_without_csrf_header(self) -> None:
        self.client.credentials()

        response = self.client.post(
            "/api/v1/interactions/view/",
            {"game_id": 5004, "source": "recommendation"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], ErrorMessages.CSRF_FAILED.name)


class CookieAuthAdminIntegrationTest(FastTestCase):
    def setUp(self) -> None:
        self.client: APIClient = make_cookie_client()
        self.admin_user = User.objects.create_superuser(
            email="cookie-admin@example.com",
            password="Admin1234!",
            nickname="cookie-admin",
            birth_date=date(1990, 1, 1),
        )
        self.normal_user = User.objects.create_user(
            email="cookie-normal@example.com",
            password="Passw0rd!",
            nickname="cookie-normal",
            birth_date=date(1996, 1, 1),
        )
        InteractionContextRule.objects.update_or_create(
            interaction_source=InteractionContextRule.InteractionSource.RECOMMENDATION,
            defaults={"multiplier": Decimal("1.40")},
        )
        InteractionWeightRule.objects.update_or_create(
            interaction_type=InteractionWeightRule.ActionType.VIEW,
            defaults={
                "base_weight": Decimal("0.20"),
                "cooldown_seconds": 60,
                "repeat_decay": Decimal("0.900"),
                "is_active": True,
            },
        )
        authenticate_client_with_cookies(self.client, self.admin_user)

    def test_admin_user_status_patch_succeeds_with_cookie_auth_and_csrf(self) -> None:
        response = self.client.patch(
            f"/api/v1/admin/users/{self.normal_user.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])

    def test_admin_interaction_context_patch_succeeds_with_cookie_auth_and_csrf(self) -> None:
        response = self.client.patch(
            "/api/v1/admin/interaction-context-rules/recommendation/",
            {"multiplier": "1.75"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["interaction_source"], "recommendation")

    def test_admin_interaction_weight_patch_succeeds_with_cookie_auth_and_csrf(self) -> None:
        response = self.client.patch(
            "/api/v1/admin/interaction-weight-rules/view/",
            {"base_weight": "0.55"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["interaction_type"], "view")

    @patch("apps.recommendations.views_admin.process_similarity_rebuild_job.delay")
    def test_admin_recommendation_job_run_succeeds_with_cookie_auth_and_csrf(self, delay_mock: object) -> None:
        response = self.client.post(
            "/api/v1/admin/recommendation-jobs/run/",
            {"job_type": RecommendationJob.JobType.SIMILARITY_REBUILD},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["type"], RecommendationJob.JobType.SIMILARITY_REBUILD)
        delay_mock.assert_called_once()  # type: ignore[attr-defined]

    def test_admin_recommendation_job_run_returns_403_without_csrf_header(self) -> None:
        self.client.credentials()

        response = self.client.post(
            "/api/v1/admin/recommendation-jobs/run/",
            {"job_type": RecommendationJob.JobType.SIMILARITY_REBUILD},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], ErrorMessages.CSRF_FAILED.name)
