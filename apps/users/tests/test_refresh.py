import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models.user import User


class RefreshAPITestCase(TestCase):
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

    def test_refresh_updates_auth_cookies(self) -> None:
        self._set_csrf_header()
        login_res = self.api_client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        old_access_token = login_res.cookies["access_token"].value
        old_refresh_token = login_res.cookies["refresh_token"].value

        self._set_csrf_header()
        res = self.api_client.post("/api/v1/auth/refresh/", format="json")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["message"], "액세스 토큰이 갱신되었습니다.")
        self.assertIn("access_token", res.cookies)
        self.assertIn("refresh_token", res.cookies)
        self.assertIn("csrftoken", res.cookies)
        self.assertTrue(res.cookies["access_token"].value)
        self.assertTrue(res.cookies["refresh_token"].value)
        self.assertNotEqual(res.cookies["access_token"].value, old_access_token)
        self.assertNotEqual(res.cookies["refresh_token"].value, old_refresh_token)

    def test_refresh_without_refresh_token(self) -> None:
        self._set_csrf_header()
        res = self.api_client.post("/api/v1/auth/refresh/", format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "REFRESH_TOKEN_MISSING")

    def test_refresh_with_invalid_refresh_token(self) -> None:
        self._set_csrf_header()
        self.api_client.cookies["refresh_token"] = "invalid.token.value"

        res = self.api_client.post("/api/v1/auth/refresh/", format="json")

        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], "INVALID_REFRESH_TOKEN")

    def test_refresh_with_deactivated_user(self) -> None:
        self._set_csrf_header()
        login_res = self.api_client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self._set_csrf_header()
        res = self.api_client.post("/api/v1/auth/refresh/", format="json")

        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], "ACCOUNT_DEACTIVATED")

    def test_refresh_ignores_invalid_access_token_cookie(self) -> None:
        self._set_csrf_header()
        login_res = self.api_client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        self.api_client.cookies["access_token"] = "invalid.token.value"
        self._set_csrf_header()
        res = self.api_client.post("/api/v1/auth/refresh/", format="json")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["message"], "액세스 토큰이 갱신되었습니다.")
