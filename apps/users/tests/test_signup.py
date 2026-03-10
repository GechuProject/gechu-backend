from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient


class SignupAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_signup_success(self) -> None:
        email = "user@example.com"
        code = "123456"

        # signup 전제조건: Redis에 인증코드가 있어야 함
        cache.set(f"email_code:{email}", code, timeout=300)

        payload = {
            "email": email,
            "code": code,
            "password": "Passw0rd!1234",
            "nickname": "gamer123",
            "birth_date": "1995-06-15",
        }

        res = self.client.post("/api/v1/auth/signup/", payload, format="json")

        self.assertEqual(res.status_code, 201)

        body = res.json()
        self.assertIn("id", body)
        self.assertEqual(body["email"], email)
        self.assertEqual(body["nickname"], payload["nickname"])
        self.assertEqual(body["birth_date"], payload["birth_date"])
        self.assertIn("created_at", body)
