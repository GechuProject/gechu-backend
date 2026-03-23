import datetime

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.auth_test_utils import authenticate_client_with_cookies, make_cookie_client
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.users.models.social_user import SocialUser


class UserPasswordChangeAPITest(FastTestCase):
    def setUp(self) -> None:
        self.client: APIClient = make_cookie_client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="change@example.com",
            password="Passw0rd!",
            nickname="changeuser",
            birth_date=datetime.date(1999, 1, 1),
        )
        self.url = reverse("users-me")

    def test_change_password_returns_200_when_password_changes(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)

        response = self.client.patch(
            self.url,
            {
                "new_password": "NewPassw0rd!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassw0rd!"))

    def test_change_password_returns_401_when_not_authenticated(self) -> None:
        response = self.client.patch(
            self.url,
            {
                "new_password": "NewPassw0rd!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_change_password_returns_400_for_social_only_user(self) -> None:
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        SocialUser.objects.create(
            user=self.user,
            provider=SocialUser.Provider.KAKAO,
            provider_uid="kakao-123",
        )
        authenticate_client_with_cookies(self.client, self.user)

        response = self.client.patch(
            self.url,
            {
                "new_password": "NewPassw0rd!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.SOCIAL_USER_ONLY.name)

    def test_change_password_returns_400_for_invalid_new_password(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)

        response = self.client.patch(
            self.url,
            {
                "new_password": "123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.VALIDATION_ERROR.name)
