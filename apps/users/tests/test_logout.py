import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models.user import User


class LogoutAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        self.user = User.objects.create_user(
            email="admin@example.com",
            nickname="admin",
            birth_date=datetime.date(1997, 10, 2),
            password="password1100110011",
        )

    def test_logout(self) -> None:
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        data = login_res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", login_res.cookies)

        access_token = data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        logout_res = self.client.post(
            "/api/v1/auth/logout/",
            format="json",
        )

        self.assertEqual(logout_res.status_code, 200)
        self.assertEqual(logout_res.json()["message"], "로그아웃 되었습니다.")

    def test_logout_without_refresh_token(self) -> None:
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)

        access_token = login_res.json()["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        self.client.cookies.pop("refresh_token", None)

        res = self.client.post(
            "/api/v1/auth/logout/",
            format="json",
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "REFRESH_TOKEN_MISSING")
