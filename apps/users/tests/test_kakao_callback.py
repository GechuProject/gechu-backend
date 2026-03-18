from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages


class KakaoCallbackAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/auth/kakao/callback/"

    def test_kakao_callback_returns_invalid_state_when_state_is_missing_in_cache(self) -> None:
        response = self.client.get(self.url, {"code": "test-code", "state": "invalid-state"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["code"], ErrorMessages.INVALID_STATE.name)

    @patch("apps.users.views.social_auth.handle_kakao_callback")
    def test_kakao_callback_returns_201_for_new_user(self, mock_handle: MagicMock) -> None:
        mock_handle.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "is_new_user": True,
        }

        response = self.client.get(self.url, {"code": "test-code", "state": "valid-state"})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.json()["is_new_user"])
        self.assertEqual(response.cookies["refresh_token"].value, "test-refresh-token")

    @patch("apps.users.views.social_auth.handle_kakao_callback")
    def test_kakao_callback_returns_200_for_existing_user(self, mock_handle: MagicMock) -> None:
        mock_handle.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "is_new_user": False,
        }

        response = self.client.get(self.url, {"code": "test-code", "state": "valid-state"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()["is_new_user"])
        self.assertEqual(response.cookies["refresh_token"].value, "test-refresh-token")
