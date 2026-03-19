from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages


class DiscordCallbackAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        self.url = reverse("auth-discord-callback")

    def test_discord_callback_returns_invalid_state_when_state_is_missing_in_cache(self) -> None:
        response = self.client.get(self.url, {"code": "test-code", "state": "invalid-state"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.INVALID_STATE.name)

    @override_settings(
        FRONTEND_BASE_URL="http://testserver",
        FRONTEND_DOMAIN=None,
        FRONTEND_SOCIAL_REDIRECT_URL=None,
        SOCIAL_LOGIN_SUCCESS_URL=None,
        SOCIAL_LOGIN_ONBOARDING_URL=None,
    )
    @patch("apps.users.views.social_auth.handle_discord_callback")
    def test_discord_callback_redirects_new_user_to_onboarding(self, mock_handle: MagicMock) -> None:
        mock_handle.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "is_new_user": True,
        }

        response = self.client.get(self.url, {"code": "test-code", "state": "valid-state"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://testserver/onboarding/")
        self.assertEqual(response.cookies["refresh_token"].value, "test-refresh-token")

    @override_settings(
        FRONTEND_BASE_URL="https://frontend.example.com",
        SOCIAL_LOGIN_SUCCESS_URL="https://frontend.example.com",
        SOCIAL_LOGIN_ONBOARDING_URL="https://frontend.example.com/onboarding",
    )
    @patch("apps.users.views.social_auth.handle_discord_callback")
    def test_discord_callback_redirects_existing_user_to_frontend_home(self, mock_handle: MagicMock) -> None:
        mock_handle.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "is_new_user": False,
        }

        response = self.client.get(self.url, {"code": "test-code", "state": "valid-state"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://frontend.example.com")
        self.assertEqual(response.cookies["refresh_token"].value, "test-refresh-token")

    @override_settings(
        FRONTEND_SOCIAL_REDIRECT_URL="https://frontend.example.com",
    )
    @patch("apps.users.views.social_auth.handle_discord_callback")
    def test_discord_callback_redirects_new_user_with_legacy_frontend_redirect(self, mock_handle: MagicMock) -> None:
        mock_handle.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "is_new_user": True,
        }

        response = self.client.get(self.url, {"code": "test-code", "state": "valid-state"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://frontend.example.com/onboarding/")
        self.assertEqual(response.cookies["refresh_token"].value, "test-refresh-token")
