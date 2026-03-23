from __future__ import annotations

from datetime import date
from typing import Any, cast

from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.games.models import ExternalStore
from apps.interactions.models import InteractionContextRule, InteractionLog, InteractionWeightRule
from apps.users.models import User

# After migration from DB-stored Game model to IGDB API:
# - game_id in requests is now an IGDB game ID (just an integer)
# - InteractionLog stores igdb_game_id instead of a FK to Game
# - No game existence validation is done (no DB lookup, no IGDB call)
# - GameStore model was deleted; store_click no longer checks game-store linkage

IGDB_GAME_ID = 6001
IGDB_GAME_ID_2 = 7001
IGDB_GAME_ID_STORE = 8001


class InteractionViewLogCreateAPITestCase(FastTestCase):
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        InteractionWeightRule.objects.create(
            interaction_type=InteractionWeightRule.ActionType.VIEW,
            base_weight=0.20,
            cooldown_seconds=150,
            repeat_decay=0.900,
            is_active=True,
        )
        InteractionContextRule.objects.bulk_create(
            [
                InteractionContextRule(
                    interaction_source=InteractionContextRule.InteractionSource.LIST_PAGE, multiplier=0.90
                ),
                InteractionContextRule(
                    interaction_source=InteractionContextRule.InteractionSource.DETAIL_PAGE, multiplier=1.20
                ),
                InteractionContextRule(
                    interaction_source=InteractionContextRule.InteractionSource.SEARCH_RESULT, multiplier=1.10
                ),
                InteractionContextRule(
                    interaction_source=InteractionContextRule.InteractionSource.RECOMMENDATION, multiplier=1.40
                ),
                InteractionContextRule(
                    interaction_source=InteractionContextRule.InteractionSource.SAVED_PAGE, multiplier=1.30
                ),
                InteractionContextRule(
                    interaction_source=InteractionContextRule.InteractionSource.ONBOARDING, multiplier=1.50
                ),
            ]
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/interactions/view/"

    def _create_user(self) -> User:
        return User.objects.create_user(
            email="user@ex.com",
            nickname="user",
            birth_date=date(1990, 1, 1),
            password="pw",
        )

    def test_interaction_view_unauthorized(self) -> None:
        response = self.client.post(self.url, {"game_id": 1, "source": "detail_page"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_interaction_view_missing_required_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(self.url, {"game_id": 1}, format="json")
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "GAME_ID_OR_SOURCE_MISSING")

    def test_interaction_view_invalid_source_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "wrong_source"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INVALID_SOURCE")

    def test_interaction_view_success(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {
                "game_id": IGDB_GAME_ID,
                "source": "recommendation",
                "metadata": {"page": 1},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        data = cast(dict[str, Any], response.data)
        self.assertIn("id", data)
        self.assertEqual(data["type"], "view")
        self.assertIn("logged_at", data)

        log = InteractionLog.objects.get(id=data["id"])
        self.assertEqual(log.user_id, user.id)
        self.assertEqual(log.igdb_game_id, IGDB_GAME_ID)
        self.assertEqual(log.type, InteractionLog.ActionType.VIEW)
        self.assertEqual(log.source, InteractionLog.SourceType.RECOMMENDATION)
        self.assertIsNotNone(log.weight)
        self.assertEqual(float(cast(Any, log.weight)), 0.28)

    def test_interaction_view_cooldown_ignored_returns_200(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        first = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(InteractionLog.objects.count(), 1)

        second = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(second.status_code, 200)
        data = cast(dict[str, Any], second.data)
        self.assertEqual(data["type"], "view")
        self.assertIn("logged_at", data)
        self.assertEqual(InteractionLog.objects.count(), 1)

    def test_interaction_view_different_source_is_logged_even_in_cooldown(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        first = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "search_result"},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(InteractionLog.objects.count(), 2)

    def test_interaction_view_recent_null_weight_log_is_not_reused_for_cooldown(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        old_log = InteractionLog.objects.create(
            user=user,
            igdb_game_id=IGDB_GAME_ID,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
            weight=None,
        )
        InteractionLog.objects.filter(id=old_log.id).update(created_at=timezone.now())

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(InteractionLog.objects.count(), 2)

    def test_interaction_view_missing_weight_rule_returns_404(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        InteractionWeightRule.objects.filter(interaction_type=InteractionWeightRule.ActionType.VIEW).delete()

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INTERACTION_TYPE_NOT_FOUND")

    def test_interaction_view_missing_source_rule_returns_404(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        InteractionContextRule.objects.filter(
            interaction_source=InteractionContextRule.InteractionSource.DETAIL_PAGE
        ).delete()

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "SOURCE_NOT_FOUND")

    def test_interaction_view_repeat_decay_applied(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        InteractionWeightRule.objects.filter(interaction_type=InteractionWeightRule.ActionType.VIEW).update(
            cooldown_seconds=0,
            repeat_decay=0.900,
        )

        first = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        first_id = cast(dict[str, Any], first.data)["id"]
        first_log = InteractionLog.objects.get(id=first_id)
        self.assertIsNotNone(first_log.weight)
        self.assertEqual(float(cast(Any, first_log.weight)), 0.24)  # 0.2 * 1.2 * 0.9^0

        second = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        second_id = cast(dict[str, Any], second.data)["id"]
        second_log = InteractionLog.objects.get(id=second_id)
        self.assertIsNotNone(second_log.weight)
        self.assertEqual(float(cast(Any, second_log.weight)), 0.216)  # 0.2 * 1.2 * 0.9^1


class InteractionSearchLogCreateAPITestCase(FastTestCase):
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        InteractionWeightRule.objects.create(
            interaction_type=InteractionWeightRule.ActionType.SEARCH,
            base_weight=0.10,
            cooldown_seconds=120,
            repeat_decay=0.900,
            is_active=True,
        )
        InteractionContextRule.objects.get_or_create(
            interaction_source=InteractionContextRule.InteractionSource.SEARCH_RESULT,
            defaults={"multiplier": 1.10},
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/interactions/search/"

    def _create_user(self) -> User:
        return User.objects.create_user(
            email="search-user@ex.com",
            nickname="search-user",
            birth_date=date(1992, 1, 1),
            password="pw",
        )

    def test_interaction_search_unauthorized(self) -> None:
        response = self.client.post(
            self.url,
            {"game_id": 1, "search_query": "elden ring", "source": "search_result"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_interaction_search_missing_search_query_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "source": "search_result"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "SEARCH_QUERY_MISSING")

    def test_interaction_search_missing_game_id_or_source_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"search_query": "elden ring", "source": "search_result"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "GAME_ID_OR_SOURCE_MISSING")

    def test_interaction_search_invalid_source_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "search_query": "elden ring", "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INVALID_SOURCE")

    def test_interaction_search_success(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {
                "game_id": IGDB_GAME_ID_2,
                "search_query": "elden ring",
                "source": "search_result",
                "metadata": {"result_rank": 3},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        data = cast(dict[str, Any], response.data)
        self.assertIn("id", data)
        self.assertEqual(data["type"], "search")
        self.assertIn("logged_at", data)

        log = InteractionLog.objects.get(id=data["id"])
        self.assertEqual(log.user_id, user.id)
        self.assertEqual(log.igdb_game_id, IGDB_GAME_ID_2)
        self.assertEqual(log.type, InteractionLog.ActionType.SEARCH)
        self.assertEqual(log.source, InteractionLog.SourceType.SEARCH_RESULT)
        self.assertEqual(log.search_query, "elden ring")
        self.assertIsNotNone(log.weight)
        self.assertEqual(float(cast(Any, log.weight)), 0.11)

    def test_interaction_search_cooldown_ignored_returns_200(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        first = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "search_query": "elden ring", "source": "search_result"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(InteractionLog.objects.count(), 1)

        second = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "search_query": "elden ring", "source": "search_result"},
            format="json",
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(InteractionLog.objects.count(), 1)

    def test_interaction_search_different_query_is_logged_even_in_cooldown(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        first = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "search_query": "elden ring", "source": "search_result"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "search_query": "stardew valley", "source": "search_result"},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(InteractionLog.objects.count(), 2)

    def test_interaction_search_missing_weight_rule_returns_404(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        InteractionWeightRule.objects.filter(interaction_type=InteractionWeightRule.ActionType.SEARCH).delete()

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "search_query": "elden ring", "source": "search_result"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INTERACTION_TYPE_NOT_FOUND")

    def test_interaction_search_missing_source_rule_returns_404(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        InteractionContextRule.objects.filter(
            interaction_source=InteractionContextRule.InteractionSource.SEARCH_RESULT
        ).delete()

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "search_query": "elden ring", "source": "search_result"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "SOURCE_NOT_FOUND")

    def test_interaction_search_repeat_decay_applied(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        InteractionWeightRule.objects.filter(interaction_type=InteractionWeightRule.ActionType.SEARCH).update(
            cooldown_seconds=0,
            repeat_decay=0.900,
        )

        first = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "search_query": "elden ring", "source": "search_result"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        first_id = cast(dict[str, Any], first.data)["id"]
        first_log = InteractionLog.objects.get(id=first_id)
        self.assertIsNotNone(first_log.weight)
        self.assertEqual(float(cast(Any, first_log.weight)), 0.11)  # 0.1 * 1.1 * 0.9^0

        second = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_2, "search_query": "elden ring", "source": "search_result"},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        second_id = cast(dict[str, Any], second.data)["id"]
        second_log = InteractionLog.objects.get(id=second_id)
        self.assertIsNotNone(second_log.weight)
        self.assertEqual(float(cast(Any, second_log.weight)), 0.099)  # 0.1 * 1.1 * 0.9^1


class InteractionStoreClickLogCreateAPITestCase(FastTestCase):
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        InteractionWeightRule.objects.create(
            interaction_type=InteractionWeightRule.ActionType.STORE_CLICK,
            base_weight=0.10,
            cooldown_seconds=120,
            repeat_decay=0.900,
            is_active=True,
        )
        InteractionContextRule.objects.get_or_create(
            interaction_source=InteractionContextRule.InteractionSource.DETAIL_PAGE,
            defaults={"multiplier": 1.20},
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/interactions/store-click/"

    def _create_user(self) -> User:
        return User.objects.create_user(
            email="store-user@ex.com",
            nickname="store-user",
            birth_date=date(1993, 1, 1),
            password="pw",
        )

    def _create_store(self, **kwargs: Any) -> ExternalStore:
        defaults: dict[str, Any] = {
            "rawg_id": 1001,
            "name": "Steam",
            "slug": "steam",
            "domain": "store.steampowered.com",
            "icon_url": "https://example.com/store-icon.png",
        }
        defaults.update(kwargs)
        return ExternalStore.objects.create(**defaults)

    def test_interaction_store_click_unauthorized(self) -> None:
        response = self.client.post(
            self.url,
            {"game_id": 1, "store_id": 1, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_interaction_store_click_missing_required_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"game_id": 1, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "GAME_ID_OR_STORE_ID_MISSING")

    def test_interaction_store_click_missing_source_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"game_id": 1, "store_id": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "GAME_ID_OR_SOURCE_MISSING")

    def test_interaction_store_click_invalid_source_returns_400(self) -> None:
        user = self._create_user()
        store = self._create_store()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": store.id, "source": "search_result"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INVALID_SOURCE")

    def test_interaction_store_click_store_not_found_returns_404(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": 999999, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "STORE_NOT_FOUND")

    def test_interaction_store_click_success(self) -> None:
        user = self._create_user()
        store = self._create_store()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {
                "game_id": IGDB_GAME_ID_STORE,
                "store_id": store.id,
                "source": "detail_page",
                "metadata": {"button_position": "hero"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        data = cast(dict[str, Any], response.data)
        self.assertIn("id", data)
        self.assertEqual(data["type"], "store_click")
        self.assertIn("logged_at", data)

        log = InteractionLog.objects.get(id=data["id"])
        self.assertEqual(log.user_id, user.id)
        self.assertEqual(log.igdb_game_id, IGDB_GAME_ID_STORE)
        self.assertEqual(log.store_id, store.id)
        self.assertEqual(log.type, InteractionLog.ActionType.STORE_CLICK)
        self.assertEqual(log.source, InteractionLog.SourceType.DETAIL_PAGE)
        self.assertIsNotNone(log.weight)
        self.assertEqual(float(cast(Any, log.weight)), 0.12)

    def test_interaction_store_click_cooldown_ignored_returns_200(self) -> None:
        user = self._create_user()
        store = self._create_store()
        self.client.force_authenticate(user=user)

        first = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": store.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(InteractionLog.objects.count(), 1)

        second = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": store.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(InteractionLog.objects.count(), 1)

    def test_interaction_store_click_different_store_is_logged_even_in_cooldown(self) -> None:
        user = self._create_user()
        store_a = self._create_store(rawg_id=1001, slug="steam", name="Steam")
        store_b = self._create_store(rawg_id=1002, slug="gog", name="GOG", domain="gog.com")
        self.client.force_authenticate(user=user)

        first = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": store_a.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": store_b.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(InteractionLog.objects.count(), 2)

    def test_interaction_store_click_missing_weight_rule_returns_404(self) -> None:
        user = self._create_user()
        store = self._create_store()
        self.client.force_authenticate(user=user)
        InteractionWeightRule.objects.filter(interaction_type=InteractionWeightRule.ActionType.STORE_CLICK).delete()

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": store.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INTERACTION_TYPE_NOT_FOUND")

    def test_interaction_store_click_missing_source_rule_returns_404(self) -> None:
        user = self._create_user()
        store = self._create_store()
        self.client.force_authenticate(user=user)
        InteractionContextRule.objects.filter(
            interaction_source=InteractionContextRule.InteractionSource.DETAIL_PAGE
        ).delete()

        response = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": store.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "SOURCE_NOT_FOUND")

    def test_interaction_store_click_repeat_decay_applied_per_store(self) -> None:
        user = self._create_user()
        store = self._create_store()
        self.client.force_authenticate(user=user)
        InteractionWeightRule.objects.filter(interaction_type=InteractionWeightRule.ActionType.STORE_CLICK).update(
            cooldown_seconds=0,
            repeat_decay=0.900,
        )

        first = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": store.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        first_id = cast(dict[str, Any], first.data)["id"]
        first_log = InteractionLog.objects.get(id=first_id)
        self.assertIsNotNone(first_log.weight)
        self.assertEqual(float(cast(Any, first_log.weight)), 0.12)  # 0.1 * 1.2 * 0.9^0

        second = self.client.post(
            self.url,
            {"game_id": IGDB_GAME_ID_STORE, "store_id": store.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        second_id = cast(dict[str, Any], second.data)["id"]
        second_log = InteractionLog.objects.get(id=second_id)
        self.assertIsNotNone(second_log.weight)
        self.assertEqual(float(cast(Any, second_log.weight)), 0.108)  # 0.1 * 1.2 * 0.9^1


class AdminInteractionWeightRuleListAPITestCase(FastTestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/admin/interaction-weight-rules/"

    def _create_user(self, *, is_staff: bool = False) -> User:
        return User.objects.create_user(
            email=f"admin-rule-{is_staff}@ex.com",
            nickname=f"admin-rule-{is_staff}",
            birth_date=date(1991, 1, 1),
            password="pw",
            is_staff=is_staff,
        )

    def test_admin_interaction_weight_rule_list_unauthorized(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_admin_interaction_weight_rule_list_forbidden_for_non_staff(self) -> None:
        user = self._create_user(is_staff=False)
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "FORBIDDEN")

    def test_admin_interaction_weight_rule_list_success(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)

        InteractionWeightRule.objects.create(
            interaction_type=InteractionWeightRule.ActionType.STORE_CLICK,
            base_weight=0.70,
            cooldown_seconds=70,
            repeat_decay=0.700,
            is_active=True,
        )
        InteractionWeightRule.objects.create(
            interaction_type=InteractionWeightRule.ActionType.VIEW,
            base_weight=1.00,
            cooldown_seconds=60,
            repeat_decay=0.800,
            is_active=True,
        )
        InteractionWeightRule.objects.create(
            interaction_type=InteractionWeightRule.ActionType.SEARCH,
            base_weight=0.90,
            cooldown_seconds=30,
            repeat_decay=0.750,
            is_active=True,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        data = cast(dict[str, Any], response.data)
        self.assertIn("results", data)
        results = cast(list[dict[str, Any]], data["results"])
        self.assertEqual([item["interaction_type"] for item in results], ["view", "search", "store_click"])

        first = results[0]
        self.assertEqual(first["base_weight"], "1.00")
        self.assertEqual(first["cooldown_seconds"], 60)
        self.assertEqual(first["repeat_decay"], "0.800")
        self.assertIn("updated_at", first)


class AdminInteractionContextRuleListAPITestCase(FastTestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/admin/interaction-context-rules/"

    def _create_user(self, *, is_staff: bool = False) -> User:
        return User.objects.create_user(
            email=f"admin-context-rule-{is_staff}@ex.com",
            nickname=f"admin-context-rule-{is_staff}",
            birth_date=date(1991, 1, 1),
            password="pw",
            is_staff=is_staff,
        )

    def test_admin_interaction_context_rule_list_unauthorized(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_admin_interaction_context_rule_list_forbidden_for_non_staff(self) -> None:
        user = self._create_user(is_staff=False)
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "FORBIDDEN")

    def test_admin_interaction_context_rule_list_success(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)

        InteractionContextRule.objects.create(
            interaction_source=InteractionContextRule.InteractionSource.RECOMMENDATION,
            multiplier=1.40,
        )
        InteractionContextRule.objects.create(
            interaction_source=InteractionContextRule.InteractionSource.LIST_PAGE,
            multiplier=0.90,
        )
        InteractionContextRule.objects.create(
            interaction_source=InteractionContextRule.InteractionSource.DETAIL_PAGE,
            multiplier=1.20,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        data = cast(dict[str, Any], response.data)
        self.assertIn("results", data)
        results = cast(list[dict[str, Any]], data["results"])
        self.assertEqual(
            [item["interaction_source"] for item in results],
            ["list_page", "detail_page", "recommendation"],
        )

        first = results[0]
        self.assertEqual(first["interaction_source"], "list_page")
        self.assertEqual(first["multiplier"], "0.90")
        self.assertIn("updated_at", first)


class AdminInteractionContextRuleUpdateAPITestCase(FastTestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/admin/interaction-context-rules/recommendation/"

    def _create_user(self, *, is_staff: bool = False) -> User:
        return User.objects.create_user(
            email=f"admin-context-update-{is_staff}@ex.com",
            nickname=f"admin-context-update-{is_staff}",
            birth_date=date(1991, 1, 1),
            password="pw",
            is_staff=is_staff,
        )

    def test_admin_interaction_context_rule_update_unauthorized(self) -> None:
        response = self.client.patch(self.url, {"multiplier": 2.0}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_admin_interaction_context_rule_update_forbidden_for_non_staff(self) -> None:
        user = self._create_user(is_staff=False)
        self.client.force_authenticate(user=user)

        response = self.client.patch(self.url, {"multiplier": 2.0}, format="json")
        self.assertEqual(response.status_code, 403)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "FORBIDDEN")

    def test_admin_interaction_context_rule_update_not_found(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            "/api/v1/admin/interaction-context-rules/unknown_source/",
            {"multiplier": 2.0},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "SOURCE_NOT_FOUND")

    def test_admin_interaction_context_rule_update_invalid_multiplier(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)
        InteractionContextRule.objects.create(
            interaction_source=InteractionContextRule.InteractionSource.RECOMMENDATION,
            multiplier=1.40,
        )

        response = self.client.patch(self.url, {"multiplier": 0}, format="json")
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "MULTIPLIER_INVALID")

    def test_admin_interaction_context_rule_update_empty_body(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)
        InteractionContextRule.objects.create(
            interaction_source=InteractionContextRule.InteractionSource.RECOMMENDATION,
            multiplier=1.40,
        )

        response = self.client.patch(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_admin_interaction_context_rule_update_success(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)
        rule = InteractionContextRule.objects.create(
            interaction_source=InteractionContextRule.InteractionSource.RECOMMENDATION,
            multiplier=1.40,
        )

        response = self.client.patch(self.url, {"multiplier": 2.0}, format="json")
        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["interaction_source"], "recommendation")
        self.assertEqual(data["multiplier"], "2.00")
        self.assertIn("updated_at", data)

        rule.refresh_from_db()
        self.assertEqual(float(cast(Any, rule.multiplier)), 2.0)


class AdminInteractionWeightRuleUpdateAPITestCase(FastTestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/admin/interaction-weight-rules/view/"

    def _create_user(self, *, is_staff: bool = False) -> User:
        return User.objects.create_user(
            email=f"admin-rule-update-{is_staff}@ex.com",
            nickname=f"admin-rule-update-{is_staff}",
            birth_date=date(1991, 1, 1),
            password="pw",
            is_staff=is_staff,
        )

    def test_admin_interaction_weight_rule_update_unauthorized(self) -> None:
        response = self.client.patch(
            self.url,
            {"base_weight": 1.50},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_interaction_weight_rule_update_forbidden_for_non_staff(self) -> None:
        user = self._create_user(is_staff=False)
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            self.url,
            {"base_weight": 1.50},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "FORBIDDEN")

    def test_admin_interaction_weight_rule_update_not_found(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            "/api/v1/admin/interaction-weight-rules/unknown/",
            {"base_weight": 1.50},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INTERACTION_TYPE_NOT_FOUND")

    def test_admin_interaction_weight_rule_update_invalid_base_weight(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)
        InteractionWeightRule.objects.create(
            interaction_type=InteractionWeightRule.ActionType.VIEW,
            base_weight=1.00,
            cooldown_seconds=60,
            repeat_decay=0.800,
            is_active=True,
        )

        response = self.client.patch(
            self.url,
            {"base_weight": 0},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "BASE_WEIGHT_INVALID")

    def test_admin_interaction_weight_rule_update_empty_body(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)
        InteractionWeightRule.objects.create(
            interaction_type=InteractionWeightRule.ActionType.VIEW,
            base_weight=1.00,
            cooldown_seconds=60,
            repeat_decay=0.800,
            is_active=True,
        )

        response = self.client.patch(
            self.url,
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "VALIDATION_ERROR")

    def test_admin_interaction_weight_rule_update_success(self) -> None:
        admin = self._create_user(is_staff=True)
        self.client.force_authenticate(user=admin)
        rule = InteractionWeightRule.objects.create(
            interaction_type=InteractionWeightRule.ActionType.VIEW,
            base_weight=1.00,
            cooldown_seconds=60,
            repeat_decay=0.800,
            is_active=True,
        )

        response = self.client.patch(
            self.url,
            {"base_weight": 1.50, "cooldown_seconds": 120},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["interaction_type"], "view")
        self.assertEqual(data["base_weight"], "1.50")
        self.assertEqual(data["cooldown_seconds"], 120)
        self.assertEqual(data["repeat_decay"], "0.800")
        self.assertIn("updated_at", data)

        rule.refresh_from_db()
        self.assertEqual(float(cast(Any, rule.base_weight)), 1.5)
        self.assertEqual(rule.cooldown_seconds, 120)


class AdminUserInteractionListAPITestCase(FastTestCase):
    client: APIClient
    admin_user: User
    target_user: User
    normal_user: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin_user = User.objects.create_user(
            email="admin-int@ex.com",
            nickname="admin-int",
            birth_date=date(1991, 1, 1),
            password="pw",
            is_staff=True,
        )
        cls.target_user = User.objects.create_user(
            email="target-int@ex.com",
            nickname="target-int",
            birth_date=date(1992, 1, 1),
            password="pw",
        )
        cls.normal_user = User.objects.create_user(
            email="normal-int@ex.com",
            nickname="normal-int",
            birth_date=date(1993, 1, 1),
            password="pw",
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.admin_user.refresh_from_db()
        self.target_user.refresh_from_db()
        self.normal_user.refresh_from_db()
        self.base_url = f"/api/v1/admin/users/{self.target_user.id}/interactions/"

    def test_admin_user_interaction_list_unauthorized(self) -> None:
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, 401)

    def test_admin_user_interaction_list_forbidden_for_non_staff(self) -> None:
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, 403)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), ErrorMessages.FORBIDDEN.name)

    def test_admin_user_interaction_list_404_when_user_not_found(self) -> None:
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/v1/admin/users/999999/interactions/")
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), ErrorMessages.USER_NOT_FOUND.name)

    def test_admin_user_interaction_list_success(self) -> None:
        InteractionLog.objects.create(
            user=self.target_user,
            igdb_game_id=IGDB_GAME_ID,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )
        InteractionLog.objects.create(
            user=self.target_user,
            igdb_game_id=IGDB_GAME_ID_2,
            type=InteractionLog.ActionType.LIKE,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertIn("next", data)
        self.assertIn("previous", data)
        self.assertEqual(data["count"], 2)
        results = cast(list[dict[str, Any]], data["results"])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["type"], "like")
        self.assertEqual(results[0]["game_id"], IGDB_GAME_ID_2)
        self.assertIn("created_at", results[0])
        self.assertEqual(results[1]["type"], "view")
        self.assertEqual(results[1]["game_id"], IGDB_GAME_ID)

    def test_admin_user_interaction_list_filter_by_type(self) -> None:
        InteractionLog.objects.create(
            user=self.target_user,
            igdb_game_id=IGDB_GAME_ID,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )
        InteractionLog.objects.create(
            user=self.target_user,
            igdb_game_id=IGDB_GAME_ID_2,
            type=InteractionLog.ActionType.LIKE,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.base_url + "?type=view")

        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["count"], 1)
        results = cast(list[dict[str, Any]], data["results"])
        self.assertEqual(results[0]["type"], "view")
        self.assertEqual(results[0]["game_id"], IGDB_GAME_ID)

    def test_admin_user_interaction_list_game_id_null_allowed(self) -> None:
        InteractionLog.objects.create(
            user=self.target_user,
            igdb_game_id=None,
            type=InteractionLog.ActionType.SEARCH,
            source=InteractionLog.SourceType.SEARCH_RESULT,
            search_query="some query",
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["count"], 1)
        results = cast(list[dict[str, Any]], data["results"])
        self.assertIsNone(results[0]["game_id"])
        self.assertEqual(results[0]["type"], "search")
