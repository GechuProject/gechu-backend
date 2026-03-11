import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages


class AuthMeAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="authme@example.com",
            password="Passw0rd!",
            nickname="authmeuser",
            birth_date=datetime.date(1999, 1, 1),
        )

    def test_auth_me_returns_current_user_info(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.user.id)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["is_active"], self.user.is_active)
        self.assertEqual(response.data["is_adult_verified"], self.user.is_adult_verified)

    def test_auth_me_returns_401_when_not_authenticated(self) -> None:
        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 401)

    def test_auth_me_returns_401_when_user_is_deleted(self) -> None:
        self.client.force_authenticate(user=self.user)
        self.user.deleted_at = timezone.now()
        self.user.save(update_fields=["deleted_at"])

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], ErrorMessages.ACCOUNT_DEACTIVATED.name)

    def test_auth_me_returns_401_when_user_is_inactive(self) -> None:
        self.client.force_authenticate(user=self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], ErrorMessages.ACCOUNT_DEACTIVATED.name)