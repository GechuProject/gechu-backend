import datetime
from typing import cast
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User


class EmailCodeSendAPITest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.email = "user@example.com"
        cache.delete(f"email_code:signup:{self.email}")
        cache.delete(f"email_code_cooldown:signup:{self.email}")
        cache.delete(f"email_code:password_reset:{self.email}")
        cache.delete(f"email_code_cooldown:password_reset:{self.email}")
        cache.delete(f"email_code_attempts:password_reset:{self.email}")
        cache.delete("email_code:password_reset:missing@example.com")
        cache.delete("email_code_cooldown:password_reset:missing@example.com")

    @patch("apps.users.services.auth_service.send_mail")
    def test_send_email_code_stores_code_in_cache(self, mock_send_mail: MagicMock) -> None:
        res = self.client.post(
            "/api/v1/auth/email/code/",
            data={"email": self.email, "purpose": "signup"},
            format="json",
        )

        drf_res = cast(Response, res)

        self.assertEqual(drf_res.status_code, 201)
        self.assertEqual(drf_res.data.get("message"), "인증 코드가 발송되었습니다.")
        self.assertEqual(drf_res.data.get("expires_in"), 300)

        code = cache.get(f"email_code:signup:{self.email}")
        self.assertIsNotNone(code)
        self.assertEqual(len(str(code)), 6)
        self.assertTrue(str(code).isdigit())
        mock_send_mail.assert_called_once()

    @patch("apps.users.services.auth_service.send_mail")
    def test_send_password_reset_code_stores_code_for_existing_user(self, mock_send_mail: MagicMock) -> None:
        User.objects.create_user(
            email=self.email,
            nickname="tester",
            birth_date=datetime.date(1997, 10, 2),
            password="OldPass1234!",
        )

        res = self.client.post(
            "/api/v1/auth/email/code/",
            data={"email": self.email, "purpose": "password_reset"},
            format="json",
        )

        drf_res = cast(Response, res)

        self.assertEqual(drf_res.status_code, 201)
        self.assertEqual(drf_res.data.get("expires_in"), 300)
        self.assertIsNotNone(cache.get(f"email_code:password_reset:{self.email}"))
        mock_send_mail.assert_called_once()

    @patch("apps.users.services.auth_service.send_mail")
    def test_send_password_reset_code_returns_same_response_for_unknown_email(self, mock_send_mail: MagicMock) -> None:
        res = self.client.post(
            "/api/v1/auth/email/code/",
            data={"email": "missing@example.com", "purpose": "password_reset"},
            format="json",
        )

        drf_res = cast(Response, res)

        self.assertEqual(drf_res.status_code, 201)
        self.assertEqual(drf_res.data.get("expires_in"), 300)
        self.assertIsNone(cache.get("email_code:password_reset:missing@example.com"))
        mock_send_mail.assert_not_called()

    @patch("apps.users.services.auth_service.send_mail")
    def test_send_signup_code_returns_conflict_for_existing_email(self, mock_send_mail: MagicMock) -> None:
        User.objects.create_user(
            email=self.email,
            nickname="tester",
            birth_date=datetime.date(1997, 10, 2),
            password="OldPass1234!",
        )

        res = self.client.post(
            "/api/v1/auth/email/code/",
            data={"email": self.email, "purpose": "signup"},
            format="json",
        )

        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["code"], ErrorMessages.EMAIL_ALREADY_EXISTS.name)
        self.assertIsNone(cache.get(f"email_code:signup:{self.email}"))
        mock_send_mail.assert_not_called()

    @patch("apps.users.services.auth_service.send_mail")
    def test_send_signup_code_returns_too_many_requests_during_cooldown(self, mock_send_mail: MagicMock) -> None:
        first_response = self.client.post(
            "/api/v1/auth/email/code/",
            data={"email": self.email, "purpose": "signup"},
            format="json",
        )
        second_response = self.client.post(
            "/api/v1/auth/email/code/",
            data={"email": self.email, "purpose": "signup"},
            format="json",
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.json()["code"], ErrorMessages.TOO_MANY_REQUESTS.name)
        mock_send_mail.assert_called_once()
