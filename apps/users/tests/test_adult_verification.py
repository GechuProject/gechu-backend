from datetime import timedelta
from typing import cast
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import requests
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models import AdultVerification, User
from apps.users.services.adult_verification_service import (
    _extract_bbaton_verification_data,
    _is_over_18,
    _request_bbaton_access_token,
    _request_bbaton_user_info,
)


@override_settings(
    BBATON_AUTHORIZE_URL="https://bauth.bbaton.com/oauth/authorize",
    BBATON_TOKEN_URL="https://bauth.bbaton.com/oauth/token",
    BBATON_USER_INFO_URL="https://bapi.bbaton.com/v2/user/me",
    BBATON_CLIENT_ID="test-client-id",
    BBATON_CLIENT_SECRET="test-client-secret",
    BBATON_REDIRECT_URI="https://example.com/api/v1/users/me/adult-verifications/callback/",
)
class AdultVerificationAPITestCase(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.client: APIClient = APIClient()
        self.user = User.objects.create_user(
            email="adult@example.com",
            password="Passw0rd!",
            nickname="adult-user",
            birth_date=timezone.localdate().replace(year=1990),
        )
        self.initiate_url = "/api/v1/users/me/adult-verifications/initiate/"
        self.callback_url = "/api/v1/users/me/adult-verifications/callback/"
        self.status_url = "/api/v1/users/me/adult-verifications/"

    def test_initiate_redirects_to_bbaton_and_saves_state(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.initiate_url)
        redirect_response = cast(HttpResponseRedirect, response)

        self.assertEqual(response.status_code, 302)
        self.assertIn("https://bauth.bbaton.com/oauth/authorize", redirect_response.url)
        query = parse_qs(urlparse(redirect_response.url).query)
        self.assertEqual(query["client_id"][0], "test-client-id")
        self.assertEqual(query["response_type"][0], "code")
        self.assertEqual(query["scope"][0], "read_profile")
        state = query["state"][0]
        self.assertEqual(cache.get(f"adult_verification_state:{state}"), {"user_id": self.user.id})

    def test_initiate_returns_401_for_unauthenticated_user(self) -> None:
        response = self.client.get(self.initiate_url)

        self.assertEqual(response.status_code, 401)

    def test_callback_returns_invalid_state_when_state_is_missing(self) -> None:
        response = self.client.get(
            self.callback_url,
            {
                "code": "test-code",
                "state": "missing-state",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.INVALID_STATE.name)

    @patch("apps.users.services.adult_verification_service._request_bbaton_user_info")
    @patch("apps.users.services.adult_verification_service._request_bbaton_access_token")
    def test_callback_completes_adult_verification(
        self,
        mock_request_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        cache.set("adult_verification_state:valid-state", {"user_id": self.user.id}, timeout=300)
        mock_request_token.return_value = "bbaton-access-token"
        mock_request_user_info.return_value = {
            "user_id": "bbaton-user-1",
            "adult_flag": "Y",
            "birth_year": "1990",
        }

        response = self.client.get(
            self.callback_url,
            {
                "code": "test-code",
                "state": "valid-state",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_adult_verified"])
        self.assertIsNotNone(response.json()["adult_verified_at"])
        self.assertIsNotNone(response.json()["expires_at"])

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_adult_verified)
        self.assertIsNotNone(self.user.adult_verified_at)
        self.assertIsNotNone(self.user.adult_verification_expires_at)
        self.assertTrue(
            AdultVerification.objects.filter(
                user=self.user,
                provider=AdultVerification.Provider.BBATON,
                provider_uid="bbaton-user-1",
            ).exists()
        )
        self.assertIsNone(cache.get("adult_verification_state:valid-state"))

    @patch("apps.users.services.adult_verification_service._request_bbaton_user_info")
    @patch("apps.users.services.adult_verification_service._request_bbaton_access_token")
    def test_callback_returns_underage_for_non_adult_user(
        self,
        mock_request_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        cache.set("adult_verification_state:underage-state", {"user_id": self.user.id}, timeout=300)
        mock_request_token.return_value = "bbaton-access-token"
        mock_request_user_info.return_value = {
            "user_id": "bbaton-user-2",
            "adult_flag": "N",
            "birth_year": "2012",
        }

        response = self.client.get(
            self.callback_url,
            {
                "code": "test-code",
                "state": "underage-state",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.UNDERAGE.name)

    def test_callback_returns_already_verified_for_valid_user(self) -> None:
        self.user.is_adult_verified = True
        self.user.adult_verified_at = timezone.now()
        self.user.adult_verification_expires_at = timezone.now() + timedelta(days=1)
        self.user.save(
            update_fields=["is_adult_verified", "adult_verified_at", "adult_verification_expires_at", "updated_at"]
        )
        cache.set("adult_verification_state:verified-state", {"user_id": self.user.id}, timeout=300)

        response = self.client.get(
            self.callback_url,
            {
                "code": "test-code",
                "state": "verified-state",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.ALREADY_VERIFIED.name)

    @patch("apps.users.services.adult_verification_service._request_bbaton_user_info")
    @patch("apps.users.services.adult_verification_service._request_bbaton_access_token")
    def test_callback_returns_conflict_for_reused_provider_uid(
        self,
        mock_request_token: MagicMock,
        mock_request_user_info: MagicMock,
    ) -> None:
        other_user = User.objects.create_user(
            email="other@example.com",
            password="Passw0rd!",
            nickname="other-user",
            birth_date=timezone.localdate().replace(year=1992),
        )
        AdultVerification.objects.create(
            user=other_user,
            provider=AdultVerification.Provider.BBATON,
            provider_uid="reused-provider-uid",
            raw_payload={},
            verified_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=365),
        )
        cache.set("adult_verification_state:reused-state", {"user_id": self.user.id}, timeout=300)
        mock_request_token.return_value = "bbaton-access-token"
        mock_request_user_info.return_value = {
            "user_id": "reused-provider-uid",
            "adult_flag": "Y",
            "birth_year": "1990",
        }

        response = self.client.get(
            self.callback_url,
            {
                "code": "test-code",
                "state": "reused-state",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], ErrorMessages.VERIFICATION_ALREADY_USED.name)

    def test_status_returns_current_adult_verification_state(self) -> None:
        verified_at = timezone.now()
        expires_at = verified_at + timedelta(days=30)
        self.user.is_adult_verified = True
        self.user.adult_verified_at = verified_at
        self.user.adult_verification_expires_at = expires_at
        self.user.save(
            update_fields=["is_adult_verified", "adult_verified_at", "adult_verification_expires_at", "updated_at"]
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.status_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_adult_verified"])
        self.assertIsNotNone(response.json()["adult_verified_at"])
        self.assertIsNotNone(response.json()["adult_verified_until"])

    def test_status_returns_false_when_verification_is_expired(self) -> None:
        self.user.is_adult_verified = True
        self.user.adult_verified_at = timezone.now() - timedelta(days=400)
        self.user.adult_verification_expires_at = timezone.now() - timedelta(days=1)
        self.user.save(
            update_fields=["is_adult_verified", "adult_verified_at", "adult_verification_expires_at", "updated_at"]
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.status_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_adult_verified"])


class AdultVerificationServiceTestCase(TestCase):
    def test_extract_bbaton_verification_data_raises_for_invalid_payload(self) -> None:
        with self.assertRaises(CustomAPIException) as context:
            _extract_bbaton_verification_data({"user_id": 123, "adult_flag": "Y"})

        self.assertEqual(context.exception.status_code, 400)

    def test_is_over_18_returns_true_with_birth_year(self) -> None:
        birth_date = timezone.localdate().replace(year=2015)

        self.assertTrue(_is_over_18(birth_date, "1990"))

    def test_is_over_18_returns_false_with_birth_date_only(self) -> None:
        birth_date = timezone.localdate().replace(year=timezone.localdate().year - 17)

        self.assertFalse(_is_over_18(birth_date))

    @override_settings(
        BBATON_TOKEN_URL="https://bauth.bbaton.com/oauth/token",
        BBATON_CLIENT_ID="test-client-id",
        BBATON_CLIENT_SECRET="test-client-secret",
        BBATON_REDIRECT_URI="https://example.com/callback/",
    )
    @patch("apps.users.services.adult_verification_service.requests.post")
    def test_request_bbaton_access_token_raises_for_request_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = requests.RequestException("boom")

        with self.assertRaises(CustomAPIException) as context:
            _request_bbaton_access_token(code="test-code")

        self.assertEqual(context.exception.status_code, 400)

    @override_settings(BBATON_USER_INFO_URL="https://bapi.bbaton.com/v2/user/me")
    @patch("apps.users.services.adult_verification_service.requests.get")
    def test_request_bbaton_user_info_raises_for_invalid_payload(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = ["not-a-dict"]
        mock_get.return_value = mock_response

        with self.assertRaises(CustomAPIException) as context:
            _request_bbaton_user_info(access_token="access-token")

        self.assertEqual(context.exception.status_code, 400)
