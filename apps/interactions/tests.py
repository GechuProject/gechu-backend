from __future__ import annotations

from datetime import date
from typing import Any, cast

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.interactions.models import InteractionContextRule, InteractionLog, InteractionWeightRule
from apps.users.models import User


class InteractionViewLogCreateAPITestCase(TestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/interactions/view/"
        self._create_view_rules()

    def _create_user(self) -> User:
        return User.objects.create_user(
            email="user@ex.com",
            nickname="user",
            birth_date=date(1990, 1, 1),
            password="pw",
        )

    def _create_game(self, **kwargs: Any) -> Any:
        from apps.games.models import Game

        defaults = {
            "rawg_id": 6001,
            "slug": "test-game",
            "name": "Test Game",
            "thumbnail_img_url": "https://example.com/thumb.jpg",
            "website": "https://example.com",
            "rawg_rating": 4.50,
            "is_visible": True,
        }
        defaults.update(kwargs)
        return Game.objects.create(**defaults)

    def _create_view_rules(self) -> None:
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
        game = self._create_game()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"game_id": game.id, "source": "wrong_source"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INVALID_SOURCE")

    def test_interaction_view_game_not_found_returns_404(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {"game_id": 999999, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "GAME_NOT_FOUND")

    def test_interaction_view_success(self) -> None:
        user = self._create_user()
        game = self._create_game()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            self.url,
            {
                "game_id": game.id,
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
        self.assertEqual(log.game_id, game.id)
        self.assertEqual(log.type, InteractionLog.ActionType.VIEW)
        self.assertEqual(log.source, InteractionLog.SourceType.RECOMMENDATION)
        self.assertIsNotNone(log.weight)
        self.assertEqual(float(cast(Any, log.weight)), 0.28)

    def test_interaction_view_cooldown_ignored_returns_200(self) -> None:
        user = self._create_user()
        game = self._create_game()
        self.client.force_authenticate(user=user)

        first = self.client.post(
            self.url,
            {"game_id": game.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(InteractionLog.objects.count(), 1)

        second = self.client.post(
            self.url,
            {"game_id": game.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(second.status_code, 200)
        data = cast(dict[str, Any], second.data)
        self.assertEqual(data["type"], "view")
        self.assertIn("logged_at", data)
        self.assertEqual(InteractionLog.objects.count(), 1)

    def test_interaction_view_recent_null_weight_log_is_not_reused_for_cooldown(self) -> None:
        user = self._create_user()
        game = self._create_game()
        self.client.force_authenticate(user=user)
        old_log = InteractionLog.objects.create(
            user=user,
            game=game,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
            weight=None,
        )
        InteractionLog.objects.filter(id=old_log.id).update(created_at=timezone.now())

        response = self.client.post(
            self.url,
            {"game_id": game.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(InteractionLog.objects.count(), 2)

    def test_interaction_view_missing_weight_rule_returns_404(self) -> None:
        user = self._create_user()
        game = self._create_game()
        self.client.force_authenticate(user=user)
        InteractionWeightRule.objects.filter(interaction_type=InteractionWeightRule.ActionType.VIEW).delete()

        response = self.client.post(
            self.url,
            {"game_id": game.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INTERACTION_TYPE_NOT_FOUND")

    def test_interaction_view_missing_source_rule_returns_404(self) -> None:
        user = self._create_user()
        game = self._create_game()
        self.client.force_authenticate(user=user)
        InteractionContextRule.objects.filter(
            interaction_source=InteractionContextRule.InteractionSource.DETAIL_PAGE
        ).delete()

        response = self.client.post(
            self.url,
            {"game_id": game.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "SOURCE_NOT_FOUND")

    def test_interaction_view_repeat_decay_applied(self) -> None:
        user = self._create_user()
        game = self._create_game()
        self.client.force_authenticate(user=user)
        InteractionWeightRule.objects.filter(interaction_type=InteractionWeightRule.ActionType.VIEW).update(
            cooldown_seconds=0,
            repeat_decay=0.900,
        )

        first = self.client.post(
            self.url,
            {"game_id": game.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        first_id = cast(dict[str, Any], first.data)["id"]
        first_log = InteractionLog.objects.get(id=first_id)
        self.assertIsNotNone(first_log.weight)
        self.assertEqual(float(cast(Any, first_log.weight)), 0.24)  # 0.2 * 1.2 * 0.9^0

        second = self.client.post(
            self.url,
            {"game_id": game.id, "source": "detail_page"},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        second_id = cast(dict[str, Any], second.data)["id"]
        second_log = InteractionLog.objects.get(id=second_id)
        self.assertIsNotNone(second_log.weight)
        self.assertEqual(float(cast(Any, second_log.weight)), 0.216)  # 0.2 * 1.2 * 0.9^1
