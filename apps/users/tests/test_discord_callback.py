from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages


class DiscordCallbackAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        self.url = reverse("auth-discord-callback")

    def test_discord_callback_returns_invalid_state_when_state_is_missing_in_cache(self) -> None:
        response = self.client.get(
            self.url,
            {
                "code": "test-code",
                "state": "invalid-state",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.INVALID_STATE.name)

    @patch("apps.users.views.social_auth.handle_discord_callback")
    def test_discord_callback_returns_social_login_response(
        self,
        mock_handle_discord_callback: MagicMock,
    ) -> None:
        mock_handle_discord_callback.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "is_new_user": True,
        }

        response = self.client.get(
            self.url,
            {
                "code": "test-code",
                "state": "valid-state",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["access_token"], "test-access-token")
        self.assertEqual(response.json()["token_type"], "Bearer")
        self.assertEqual(response.json()["expires_in"], 3600)
        self.assertEqual(response.json()["is_new_user"], True)
        self.assertEqual(response.cookies["refresh_token"].value, "test-refresh-token")
