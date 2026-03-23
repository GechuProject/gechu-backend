import datetime

from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.users.models.user import User


class LoginAPITestCase(FastTestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            email="admin@example.com",
            nickname="admin",
            birth_date=datetime.date(1997, 10, 2),
            password="password1100110011",
        )

    def _set_csrf_header(self) -> str:
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        csrf_token = str(response.json()["csrf_token"])
        self.client.credentials(HTTP_X_CSRFTOKEN=csrf_token)
        return csrf_token

    def test_login_sets_auth_and_csrf_cookies(self) -> None:
        self._set_csrf_header()
        res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["message"], "로그인 되었습니다.")
        self.assertIn("access_token", res.cookies)
        self.assertIn("refresh_token", res.cookies)
        self.assertIn("csrftoken", res.cookies)
        self.assertTrue(res.cookies["access_token"].value)
        self.assertTrue(res.cookies["refresh_token"].value)
        self.assertTrue(res.cookies["csrftoken"].value)
        self.assertTrue(res.cookies["access_token"]["httponly"])
        self.assertTrue(res.cookies["refresh_token"]["httponly"])

    def test_login_requires_csrf(self) -> None:
        res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )

        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["code"], ErrorMessages.CSRF_FAILED.name)

    def test_auth_csrf_returns_token_and_cookie(self) -> None:
        res = self.client.get("/api/v1/auth/csrf/")

        self.assertEqual(res.status_code, 200)
        self.assertIn("csrf_token", res.json())
        self.assertIn("csrftoken", res.cookies)
        self.assertTrue(res.json()["csrf_token"])
        self.assertTrue(res.cookies["csrftoken"].value)

    def test_login_invalid_password(self) -> None:
        self._set_csrf_header()
        res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "oh.no"},
            format="json",
        )

        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], ErrorMessages.INVALID_CREDENTIALS.name)

    def test_login_none_email(self) -> None:
        self._set_csrf_header()
        res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "nonexistent@example.com", "password": "oh.no"},
            format="json",
        )

        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], ErrorMessages.INVALID_CREDENTIALS.name)

    def test_login_deleted_user_returns_401(self) -> None:
        self.user.deleted_at = timezone.now()
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])

        self._set_csrf_header()
        res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )

        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], ErrorMessages.ACCOUNT_DEACTIVATED.name)
