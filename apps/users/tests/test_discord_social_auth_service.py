from datetime import date
from typing import Any, cast
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.social_user import SocialUser
from apps.users.services.social_auth_service import (
    DEFAULT_SOCIAL_BIRTH_DATE,
    handle_discord_callback,
    request_discord_access_token,
    request_discord_user_info,
)

User = get_user_model()


@override_settings(
    DISCORD_CLIENT_ID="discord-client-id",
    DISCORD_CLIENT_SECRET="discord-client-secret",
    DISCORD_REDIRECT_URI="https://example.com/auth/discord/callback/",
    DISCORD_TOKEN_URL="https://discord.example.com/api/oauth2/token",
    DISCORD_USER_INFO_URL="https://discord.example.com/api/users/@me",
)
class DiscordSocialAuthServiceTestCase(TestCase):
    def test_request_discord_access_token_returns_access_token(self) -> None:
        with patch("apps.users.services.social_auth_service.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"access_token": "discord-access-token"}
            mock_post.return_value = mock_response

            access_token = request_discord_access_token(code="test-code")

        self.assertEqual(access_token, "discord-access-token")
        mock_post.assert_called_once_with(
            "https://discord.example.com/api/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "discord-client-id",
                "client_secret": "discord-client-secret",
                "redirect_uri": "https://example.com/auth/discord/callback/",
                "code": "test-code",
            },
            timeout=5,
        )

    def test_request_discord_access_token_raises_for_request_error(self) -> None:
        with patch(
            "apps.users.services.social_auth_service.requests.post",
            side_effect=requests.RequestException,
        ):
            with self.assertRaises(CustomAPIException) as context:
                request_discord_access_token(code="test-code")

        detail = cast(dict[str, Any], context.exception.detail)
        self.assertEqual(detail["code"], ErrorMessages.DISCORD_OAUTH_CALLBACK_ERROR.name)

    def test_request_discord_user_info_returns_payload(self) -> None:
        with patch("apps.users.services.social_auth_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "discord-user-id",
                "email": "discord@example.com",
            }
            mock_get.return_value = mock_response

            user_info = request_discord_user_info(access_token="discord-access-token")

        self.assertEqual(user_info["id"], "discord-user-id")
        self.assertEqual(user_info["email"], "discord@example.com")
        mock_get.assert_called_once_with(
            "https://discord.example.com/api/users/@me",
            headers={
                "Authorization": "Bearer discord-access-token",
            },
            timeout=5,
        )

    def test_request_discord_user_info_raises_for_invalid_payload(self) -> None:
        with patch("apps.users.services.social_auth_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = []
            mock_get.return_value = mock_response

            with self.assertRaises(CustomAPIException) as context:
                request_discord_user_info(access_token="discord-access-token")

        detail = cast(dict[str, Any], context.exception.detail)
        self.assertEqual(detail["code"], ErrorMessages.DISCORD_OAUTH_CALLBACK_ERROR.name)

    @patch("apps.users.services.social_auth_service.request_discord_user_info")
    @patch("apps.users.services.social_auth_service.request_discord_access_token")
    def test_handle_discord_callback_creates_new_user(
        self,
        mock_request_access_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        cache.set("oauth_state:discord:valid-state", True, timeout=300)
        mock_request_access_token.return_value = "discord-access-token"
        mock_request_user_info.return_value = {
            "id": "discord-user-1",
            "email": "discord-new@example.com",
        }

        result = handle_discord_callback(code="test-code", state="valid-state")

        user = User.objects.get(email="discord-new@example.com")
        social_user = SocialUser.objects.get(
            provider=SocialUser.Provider.DISCORD,
            provider_uid="discord-user-1",
        )

        self.assertEqual(social_user.user_id, user.id)
        self.assertEqual(user.birth_date, DEFAULT_SOCIAL_BIRTH_DATE)
        self.assertTrue(result["is_new_user"])
        self.assertIsNone(cache.get("oauth_state:discord:valid-state"))

    @patch("apps.users.services.social_auth_service.request_discord_user_info")
    @patch("apps.users.services.social_auth_service.request_discord_access_token")
    def test_handle_discord_callback_links_existing_user_by_email(
        self,
        mock_request_access_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        existing_user = User.objects.create_user(
            email="existing@example.com",
            nickname="existing-user",
            birth_date=date(1998, 1, 1),
            password="Passw0rd!",
        )
        cache.set("oauth_state:discord:valid-state", True, timeout=300)
        mock_request_access_token.return_value = "discord-access-token"
        mock_request_user_info.return_value = {
            "id": "discord-user-2",
            "email": "existing@example.com",
        }

        result = handle_discord_callback(code="test-code", state="valid-state")

        social_user = SocialUser.objects.get(
            provider=SocialUser.Provider.DISCORD,
            provider_uid="discord-user-2",
        )

        self.assertEqual(social_user.user_id, existing_user.id)
        self.assertFalse(result["is_new_user"])

    @patch("apps.users.services.social_auth_service.request_discord_user_info")
    @patch("apps.users.services.social_auth_service.request_discord_access_token")
    def test_handle_discord_callback_returns_existing_social_user(
        self,
        mock_request_access_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        existing_user = User.objects.create_user(
            email="discord-existing@example.com",
            nickname="discord-existing",
            birth_date=date(1997, 1, 1),
            password="Passw0rd!",
        )
        SocialUser.objects.create(
            user=existing_user,
            provider=SocialUser.Provider.DISCORD,
            provider_uid="discord-user-3",
        )
        cache.set("oauth_state:discord:valid-state", True, timeout=300)
        mock_request_access_token.return_value = "discord-access-token"
        mock_request_user_info.return_value = {
            "id": "discord-user-3",
            "email": "discord-existing@example.com",
        }

        result = handle_discord_callback(code="test-code", state="valid-state")

        self.assertFalse(result["is_new_user"])
        self.assertEqual(User.objects.filter(email="discord-existing@example.com").count(), 1)
