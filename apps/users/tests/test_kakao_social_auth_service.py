from datetime import date
from typing import Any, cast
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import override_settings

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.users.models.social_user import SocialUser
from apps.users.models.user import User
from apps.users.services.social_auth_service import (
    DEFAULT_SOCIAL_BIRTH_DATE,
    extract_kakao_user_data,
    handle_kakao_callback,
    request_kakao_access_token,
    request_kakao_user_info,
)


@override_settings(
    KAKAO_CLIENT_ID="kakao-client-id",
    KAKAO_CLIENT_SECRET="kakao-client-secret",
    KAKAO_REDIRECT_URI="https://example.com/auth/kakao/callback/",
)
class KakaoSocialAuthServiceTestCase(FastTestCase):
    existing_user: User
    social_linked_user: User
    duplicate_nickname_user: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.existing_user = User.objects.create_user(
            email="existing-kakao@example.com",
            nickname="existing-kakao",
            birth_date=date(1998, 1, 1),
            password="Passw0rd!",
        )
        cls.social_linked_user = User.objects.create_user(
            email="kakao-social@example.com",
            nickname="kakao-social",
            birth_date=date(1997, 1, 1),
            password="Passw0rd!",
        )
        SocialUser.objects.create(
            user=cls.social_linked_user,
            provider=SocialUser.Provider.KAKAO,
            provider_uid="33333",
        )
        cls.duplicate_nickname_user = User.objects.create_user(
            email="other-kakao@example.com",
            nickname="duplicate-nickname",
            birth_date=date(2000, 1, 1),
            password=None,
        )

    # --- request_kakao_access_token ---

    def test_request_kakao_access_token_returns_access_token(self) -> None:
        with patch("apps.users.services.social_auth_service._make_session") as mock_make_session:
            mock_session = MagicMock()
            mock_make_session.return_value = mock_session
            mock_response = MagicMock()
            mock_response.json.return_value = {"access_token": "kakao-access-token"}
            mock_session.post.return_value = mock_response

            access_token = request_kakao_access_token(code="test-code")

        self.assertEqual(access_token, "kakao-access-token")
        mock_session.post.assert_called_once_with(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "kakao-client-id",
                "redirect_uri": "https://example.com/auth/kakao/callback/",
                "client_secret": "kakao-client-secret",
                "code": "test-code",
            },
            timeout=5,
        )

    def test_request_kakao_access_token_raises_for_request_error(self) -> None:
        with patch("apps.users.services.social_auth_service._make_session") as mock_make_session:
            mock_session = MagicMock()
            mock_make_session.return_value = mock_session
            mock_session.post.side_effect = requests.RequestException

            with self.assertLogs("apps.users.services.social_auth_service", level="ERROR"):
                with self.assertRaises(CustomAPIException) as context:
                    request_kakao_access_token(code="test-code")

        detail = cast(dict[str, Any], context.exception.detail)
        self.assertEqual(detail["code"], ErrorMessages.OAUTH_CALLBACK_ERROR.name)

    def test_request_kakao_access_token_raises_when_token_missing_in_response(self) -> None:
        with patch("apps.users.services.social_auth_service._make_session") as mock_make_session:
            mock_session = MagicMock()
            mock_make_session.return_value = mock_session
            mock_response = MagicMock()
            mock_response.json.return_value = {"error": "invalid_grant"}
            mock_session.post.return_value = mock_response

            with self.assertLogs("apps.users.services.social_auth_service", level="ERROR"):
                with self.assertRaises(CustomAPIException) as context:
                    request_kakao_access_token(code="test-code")

        detail = cast(dict[str, Any], context.exception.detail)
        self.assertEqual(detail["code"], ErrorMessages.OAUTH_CALLBACK_ERROR.name)

    # --- request_kakao_user_info ---

    def test_request_kakao_user_info_returns_payload(self) -> None:
        with patch("apps.users.services.social_auth_service._make_session") as mock_make_session:
            mock_session = MagicMock()
            mock_make_session.return_value = mock_session
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": 12345, "kakao_account": {"email": "kakao@example.com"}}
            mock_session.get.return_value = mock_response

            user_info = request_kakao_user_info(access_token="kakao-access-token")

        self.assertEqual(user_info["id"], 12345)
        mock_session.get.assert_called_once_with(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": "Bearer kakao-access-token"},
            timeout=5,
        )

    def test_request_kakao_user_info_raises_for_request_error(self) -> None:
        with patch("apps.users.services.social_auth_service._make_session") as mock_make_session:
            mock_session = MagicMock()
            mock_make_session.return_value = mock_session
            mock_session.get.side_effect = requests.RequestException

            with self.assertLogs("apps.users.services.social_auth_service", level="ERROR"):
                with self.assertRaises(CustomAPIException) as context:
                    request_kakao_user_info(access_token="kakao-access-token")

        detail = cast(dict[str, Any], context.exception.detail)
        self.assertEqual(detail["code"], ErrorMessages.OAUTH_CALLBACK_ERROR.name)

    def test_request_kakao_user_info_raises_for_invalid_payload(self) -> None:
        with patch("apps.users.services.social_auth_service._make_session") as mock_make_session:
            mock_session = MagicMock()
            mock_make_session.return_value = mock_session
            mock_response = MagicMock()
            mock_response.json.return_value = []
            mock_session.get.return_value = mock_response

            with self.assertLogs("apps.users.services.social_auth_service", level="ERROR"):
                with self.assertRaises(CustomAPIException) as context:
                    request_kakao_user_info(access_token="kakao-access-token")

        detail = cast(dict[str, Any], context.exception.detail)
        self.assertEqual(detail["code"], ErrorMessages.OAUTH_CALLBACK_ERROR.name)

    # --- extract_kakao_user_data ---

    def test_extract_kakao_user_data_returns_full_data_with_email_and_birthdate(self) -> None:
        user_info = {
            "id": 99999,
            "kakao_account": {
                "email": "kakao@example.com",
                "birthyear": "1995",
                "birthday": "0315",
            },
        }

        provider_uid, email, birth_date = extract_kakao_user_data(user_info)

        self.assertEqual(provider_uid, "99999")
        self.assertEqual(email, "kakao@example.com")
        self.assertEqual(birth_date, date(1995, 3, 15))

    def test_extract_kakao_user_data_returns_default_birthdate_when_missing(self) -> None:
        user_info = {"id": 99999, "kakao_account": {"email": "kakao@example.com"}}

        _, _, birth_date = extract_kakao_user_data(user_info)

        self.assertEqual(birth_date, DEFAULT_SOCIAL_BIRTH_DATE)

    def test_extract_kakao_user_data_uses_fallback_email_when_missing(self) -> None:
        user_info = {"id": 99999, "kakao_account": {}}

        _, email, _ = extract_kakao_user_data(user_info)

        self.assertEqual(email, "kakao_99999@social.gechu")

    def test_extract_kakao_user_data_raises_when_id_missing(self) -> None:
        with self.assertRaises(CustomAPIException) as context:
            extract_kakao_user_data({})

        detail = cast(dict[str, Any], context.exception.detail)
        self.assertEqual(detail["code"], ErrorMessages.OAUTH_CALLBACK_ERROR.name)

    # --- handle_kakao_callback ---

    @patch("apps.users.services.social_auth_service.request_kakao_user_info")
    @patch("apps.users.services.social_auth_service.request_kakao_access_token")
    def test_handle_kakao_callback_creates_new_user(
        self,
        mock_request_access_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        cache.set("oauth_state:valid-state", "kakao", timeout=300)
        mock_request_access_token.return_value = "kakao-access-token"
        mock_request_user_info.return_value = {
            "id": 11111,
            "kakao_account": {"email": "kakao-new@example.com"},
        }

        result = handle_kakao_callback(code="test-code", state="valid-state")

        user = User.objects.get(email="kakao-new@example.com")
        social_user = SocialUser.objects.get(
            provider=SocialUser.Provider.KAKAO,
            provider_uid="11111",
        )
        self.assertEqual(social_user.user_id, user.id)
        self.assertTrue(result["is_new_user"])
        self.assertIsNone(cache.get("oauth_state:valid-state"))

    @patch("apps.users.services.social_auth_service.request_kakao_user_info")
    @patch("apps.users.services.social_auth_service.request_kakao_access_token")
    def test_handle_kakao_callback_links_existing_user_by_email(
        self,
        mock_request_access_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        cache.set("oauth_state:valid-state", "kakao", timeout=300)
        mock_request_access_token.return_value = "kakao-access-token"
        mock_request_user_info.return_value = {
            "id": 22222,
            "kakao_account": {"email": self.existing_user.email},
        }

        result = handle_kakao_callback(code="test-code", state="valid-state")

        social_user = SocialUser.objects.get(
            provider=SocialUser.Provider.KAKAO,
            provider_uid="22222",
        )
        self.assertEqual(social_user.user_id, self.existing_user.id)
        self.assertFalse(result["is_new_user"])

    @patch("apps.users.services.social_auth_service.request_kakao_user_info")
    @patch("apps.users.services.social_auth_service.request_kakao_access_token")
    def test_handle_kakao_callback_returns_existing_social_user(
        self,
        mock_request_access_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        cache.set("oauth_state:valid-state", "kakao", timeout=300)
        mock_request_access_token.return_value = "kakao-access-token"
        mock_request_user_info.return_value = {
            "id": 33333,
            "kakao_account": {"email": self.social_linked_user.email},
        }

        result = handle_kakao_callback(code="test-code", state="valid-state")

        self.assertFalse(result["is_new_user"])
        self.assertEqual(User.objects.filter(email=self.social_linked_user.email).count(), 1)

    @patch("apps.users.services.social_auth_service.request_kakao_user_info")
    @patch("apps.users.services.social_auth_service.request_kakao_access_token")
    def test_handle_kakao_callback_creates_new_user_with_fallback_email(
        self,
        mock_request_access_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        cache.set("oauth_state:valid-state", "kakao", timeout=300)
        mock_request_access_token.return_value = "kakao-access-token"
        mock_request_user_info.return_value = {"id": 44444, "kakao_account": {}}

        result = handle_kakao_callback(code="test-code", state="valid-state")

        user = User.objects.get(email="kakao_44444@social.gechu")
        self.assertTrue(result["is_new_user"])
        self.assertEqual(user.email, "kakao_44444@social.gechu")

    @patch("apps.users.services.social_auth_service.generate_unique_nickname")
    @patch("apps.users.services.social_auth_service.request_kakao_user_info")
    @patch("apps.users.services.social_auth_service.request_kakao_access_token")
    def test_handle_kakao_callback_uses_uuid_fallback_after_nickname_exhaustion(
        self,
        mock_request_access_token: MagicMock,
        mock_request_user_info: MagicMock,
        mock_generate_nickname: MagicMock,
    ) -> None:
        cache.set("oauth_state:valid-state", "kakao", timeout=300)
        mock_request_access_token.return_value = "kakao-access-token"
        mock_request_user_info.return_value = {
            "id": 55555,
            "kakao_account": {"email": "nickname-fail@example.com"},
        }
        mock_generate_nickname.return_value = self.duplicate_nickname_user.nickname

        with self.assertLogs("apps.users.services.social_auth_service", level="WARNING"):
            result = handle_kakao_callback(code="test-code", state="valid-state")

        user = User.objects.get(email="nickname-fail@example.com")
        self.assertTrue(result["is_new_user"])
        self.assertNotEqual(user.nickname, self.duplicate_nickname_user.nickname)
        self.assertLessEqual(len(user.nickname), 30)
