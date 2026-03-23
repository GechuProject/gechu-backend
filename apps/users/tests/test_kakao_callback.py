from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages


class KakaoCallbackAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/auth/kakao/callback/"

    def _parse_redirect_params(self, response: Any) -> dict[str, str]:
        location = response["Location"]
        query = urlparse(location).query
        return {k: v[0] for k, v in parse_qs(query).items()}

    def test_kakao_callback_redirects_with_error_when_state_is_invalid(self) -> None:
        response = self.client.get(self.url, {"code": "test-code", "state": "invalid-state"})

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        params = self._parse_redirect_params(response)
        self.assertEqual(params["error"], ErrorMessages.INVALID_STATE.name)
        self.assertIn("error_description", params)

    @patch("apps.users.views.social_auth.handle_kakao_callback")
    def test_kakao_callback_redirects_with_access_token_for_new_user(self, mock_handle: MagicMock) -> None:
        mock_handle.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "is_new_user": True,
        }

        response = self.client.get(self.url, {"code": "test-code", "state": "valid-state"})

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        params = self._parse_redirect_params(response)
        self.assertNotIn("access_token", params)
        self.assertEqual(params["is_new_user"], "true")
        self.assertEqual(response.cookies["access_token"].value, "test-access-token")
        self.assertEqual(response.cookies["refresh_token"].value, "test-refresh-token")

    @patch("apps.users.views.social_auth.handle_kakao_callback")
    def test_kakao_callback_redirects_with_access_token_for_existing_user(self, mock_handle: MagicMock) -> None:
        mock_handle.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "is_new_user": False,
        }

        response = self.client.get(self.url, {"code": "test-code", "state": "valid-state"})

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        params = self._parse_redirect_params(response)
        self.assertNotIn("access_token", params)
        self.assertEqual(params["is_new_user"], "false")
        self.assertEqual(response.cookies["access_token"].value, "test-access-token")
        self.assertEqual(response.cookies["refresh_token"].value, "test-refresh-token")

    @patch("apps.users.views.social_auth.handle_kakao_callback")
    def test_kakao_callback_redirects_with_error_on_server_exception(self, mock_handle: MagicMock) -> None:
        mock_handle.side_effect = Exception("unexpected error")

        with self.assertLogs("apps.users.views.social_auth", level="ERROR"):
            response = self.client.get(self.url, {"code": "test-code", "state": "valid-state"})

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        params = self._parse_redirect_params(response)
        self.assertEqual(params["error"], "SERVER_ERROR")
        self.assertIn("error_description", params)
