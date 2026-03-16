import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.social_user import SocialUser


class UserPasswordVerifyAPITest(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="verify@example.com",
            password="Passw0rd!",
            nickname="verifyuser",
            birth_date=datetime.date(1999, 1, 1),
        )
        self.url = "/api/v1/users/me/verify-password/"

    def test_verify_password_returns_200_when_password_matches(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"password": "Passw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "비밀번호가 확인되었습니다.")

    def test_verify_password_returns_401_when_not_authenticated(self) -> None:
        response = self.client.post(
            self.url,
            {"password": "Passw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_verify_password_returns_401_when_password_is_invalid(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], ErrorMessages.INVALID_PASSWORD.name)

    def test_verify_password_returns_400_for_social_only_user(self) -> None:
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        SocialUser.objects.create(
            user=self.user,
            provider=SocialUser.Provider.KAKAO,
            provider_uid="kakao-123",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"password": "Passw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.SOCIAL_USER_ONLY.name)

    def test_verify_password_returns_401_for_deactivated_user(self) -> None:
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"password": "Passw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], ErrorMessages.ACCOUNT_DEACTIVATED.name)
