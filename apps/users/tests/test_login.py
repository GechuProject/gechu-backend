from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models.user import User
import datetime

class LoginAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(email='admin@example.com',nickname= "admin",birth_date = datetime.date(1997, 10, 2), password='password1100110011')

    def test_login(self):
        # 로그인 요청
        res = self.client.post(
            "/api/v1/auth/login",
            {"email": "admin@example.com", "password": "password1100110011"},
            format="json",
        )

        # 성공 응답
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("access_token", data)
        self.assertTrue(data["access_token"])  # 빈 문자열/None이면 실패
        self.assertEqual(data["token_type"], "Bearer")
        self.assertEqual(data["expires_in"], 3600)

    # 비밀번호 오류
    def test_login_invalid_password(self):
        res = self.client.post(
            "/api/v1/auth/login",
            {"email": "admin@example.com", "password": "oh.no"},
            format="json",
        )

        # 실패 응답
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("INVALID_CREDENTIALS", str(data))

    # 이메일 오류
    def test_login_none_email(self):
        res = self.client.post(
            "/api/v1/auth/login",
            {"email": "None@example.com", "password": "oh.no"},
            format="json",
        )

        # 실패 응답
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("INVALID_CREDENTIALS", str(data))
