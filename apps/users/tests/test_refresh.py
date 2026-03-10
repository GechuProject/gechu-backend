import datetime
from datetime import timedelta
from typing import cast

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models.user import User


class RefreshAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="admin@example.com",
            nickname="admin",
            birth_date=datetime.date(1997, 10, 2),
            password="password1100110011",
        )

    def test_refresh(self) -> None:
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("refresh_token", login_res.cookies)

        res = self.client.post(
            "/api/v1/auth/refresh/",
            format="json",
        )

        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("access_token", data)
        self.assertTrue(data["access_token"])
        self.assertEqual(data["token_type"], "Bearer")
        self.assertEqual(
            data["expires_in"],
            int(
                cast(
                    timedelta,
                    settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
                ).total_seconds()
            ),
        )

    def test_refresh_without_refresh_token(self) -> None:
        res = self.client.post(
            "/api/v1/auth/refresh/",
            format="json",
        )

        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertEqual(data["code"], "REFRESH_TOKEN_MISSING")

    def test_refresh_with_invalid_refresh_token(self) -> None:
        self.client.cookies["refresh_token"] = "invalid.token.value"

        res = self.client.post(
            "/api/v1/auth/refresh/",
            format="json",
        )

        self.assertEqual(res.status_code, 401)
        data = res.json()
        self.assertEqual(data["code"], "INVALID_REFRESH_TOKEN")

    def test_refresh_with_deactivated_user(self) -> None:
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        res = self.client.post(
            "/api/v1/auth/refresh/",
            format="json",
        )

        self.assertEqual(res.status_code, 401)
        data = res.json()
        self.assertEqual(data["code"], "ACCOUNT_DEACTIVATED")
