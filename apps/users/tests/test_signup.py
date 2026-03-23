import datetime

from django.core.cache import cache
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.users.models.user import User


class SignupAPITestCase(FastTestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.email = "user@example.com"
        cache.delete(f"email_code:signup:{self.email}")
        cache.delete(f"email_code_attempts:signup:{self.email}")

    def test_signup_success(self) -> None:
        email = self.email
        code = "123456"

        # signup 전제조건: Redis에 인증코드가 있어야 함
        cache.set(f"email_code:signup:{email}", code, timeout=300)

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

    def test_signup_returns_conflict_for_existing_email(self) -> None:
        email = self.email
        code = "123456"
        User.objects.create_user(
            email=email,
            nickname="existing-user",
            birth_date=datetime.date(1990, 1, 1),
            password="Passw0rd!1234",
        )
        cache.set(f"email_code:signup:{email}", code, timeout=300)

        payload = {
            "email": email,
            "code": code,
            "password": "Passw0rd!1234",
            "nickname": "gamer123",
            "birth_date": "1995-06-15",
        }

        res = self.client.post("/api/v1/auth/signup/", payload, format="json")

        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["code"], ErrorMessages.EMAIL_ALREADY_EXISTS.name)

    def test_signup_returns_conflict_for_existing_nickname(self) -> None:
        email = "user@example.com"
        code = "123456"
        User.objects.create_user(
            email="other@example.com",
            nickname="gamer123",
            birth_date=datetime.date(1990, 1, 1),
            password="Passw0rd!1234",
        )
        cache.set(f"email_code:signup:{email}", code, timeout=300)

        payload = {
            "email": email,
            "code": code,
            "password": "Passw0rd!1234",
            "nickname": "gamer123",
            "birth_date": "1995-06-15",
        }

        res = self.client.post("/api/v1/auth/signup/", payload, format="json")

        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["code"], ErrorMessages.NICKNAME_ALREADY_EXISTS.name)

    def test_signup_returns_code_expired_when_cached_code_missing(self) -> None:
        payload = {
            "email": self.email,
            "code": "123456",
            "password": "Passw0rd!1234",
            "nickname": "gamer123",
            "birth_date": "1995-06-15",
        }

        res = self.client.post("/api/v1/auth/signup/", payload, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], ErrorMessages.CODE_EXPIRED.name)

    def test_signup_returns_invalid_code_for_mismatched_verification_code(self) -> None:
        email = self.email
        cache.set(f"email_code:signup:{email}", "654321", timeout=300)

        payload = {
            "email": email,
            "code": "123456",
            "password": "Passw0rd!1234",
            "nickname": "gamer123",
            "birth_date": "1995-06-15",
        }

        res = self.client.post("/api/v1/auth/signup/", payload, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], ErrorMessages.INVALID_CODE.name)

    def test_signup_returns_validation_error_for_invalid_password(self) -> None:
        email = self.email
        code = "123456"
        cache.set(f"email_code:signup:{email}", code, timeout=300)

        payload = {
            "email": email,
            "code": code,
            "password": "1234",
            "nickname": "gamer123",
            "birth_date": "1995-06-15",
        }

        res = self.client.post("/api/v1/auth/signup/", payload, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], ErrorMessages.VALIDATION_ERROR.name)
