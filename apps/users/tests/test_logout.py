import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User


class LogoutAPITestCase(TestCase):
    def setUp(self) -> None:
        self.api_client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            email="admin@example.com",
            nickname="admin",
            birth_date=datetime.date(1997, 10, 2),
            password="password1100110011",
        )

    def _set_csrf_header(self) -> str:
        response = self.api_client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        csrf_token = str(response.json()["csrf_token"])
        self.api_client.credentials(HTTP_X_CSRFTOKEN=csrf_token)
        return csrf_token

    def test_logout_clears_auth_cookies(self) -> None:
        login_res = self.api_client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        self._set_csrf_header()
        logout_res = self.api_client.post("/api/v1/auth/logout/", format="json")

        self.assertEqual(logout_res.status_code, 200)
        self.assertEqual(logout_res.json()["message"], "로그아웃 되었습니다.")
        self.assertEqual(logout_res.cookies["refresh_token"].value, "")
        self.assertEqual(logout_res.cookies["access_token"].value, "")

    def test_logout_deletes_access_token_cookie(self) -> None:
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        access_token = login_res.json()["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        self.client.cookies["access_token"] = access_token

        logout_res = self.client.post(
            "/api/v1/auth/logout/",
            format="json",
        )

        self.assertEqual(logout_res.status_code, 200)
        self.assertIn("access_token", logout_res.cookies)
        self.assertEqual(logout_res.cookies["access_token"].value, "")

    def test_logout_without_refresh_token(self) -> None:
        login_res = self.api_client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        self.api_client.cookies.pop("refresh_token", None)
        self._set_csrf_header()
        res = self.api_client.post("/api/v1/auth/logout/", format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "REFRESH_TOKEN_MISSING")

    def test_logout_requires_csrf(self) -> None:
        login_res = self.api_client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        res = self.api_client.post("/api/v1/auth/logout/", format="json")

        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["code"], ErrorMessages.CSRF_FAILED.name)
