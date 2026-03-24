import datetime
from typing import cast

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.core.auth_test_utils import authenticate_client_with_cookies, make_cookie_client
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.users.services import issue_auth_tokens


class AuthMeAPITestCase(FastTestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(
            email="authme@example.com",
            password="Passw0rd!",
            nickname="authmeuser",
            birth_date=datetime.date(1999, 1, 1),
        )
        self.url = reverse("auth-me")

    def _set_csrf_header(self) -> str:
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        csrf_token = str(response.json()["csrf_token"])
        self.client.credentials(HTTP_X_CSRFTOKEN=csrf_token)
        return csrf_token

    def test_auth_me_returns_current_user_info_from_login_cookie(self) -> None:
        self._set_csrf_header()
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "authme@example.com", "password": "Passw0rd!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)

        res = self.client.get(self.url)
        drf_res = cast(Response, res)

        self.assertEqual(drf_res.status_code, 200)
        self.assertEqual(
            drf_res.data,
            {
                "id": self.user.id,
                "email": self.user.email,
                "is_active": self.user.is_active,
                "is_staff": self.user.is_staff,
                "is_adult_verified": self.user.is_adult_verified,
            },
        )

    def test_auth_me_returns_401_when_not_authenticated(self) -> None:
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_auth_me_returns_401_when_user_is_deleted(self) -> None:
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)
        self.user.deleted_at = timezone.now()
        self.user.save(update_fields=["deleted_at"])

        response = client.get(self.url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], ErrorMessages.ACCOUNT_DEACTIVATED.name)

    def test_auth_me_returns_401_when_user_is_inactive(self) -> None:
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = client.get(self.url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], ErrorMessages.ACCOUNT_DEACTIVATED.name)

    def test_auth_me_rejects_bearer_header_without_auth_cookie(self) -> None:
        access_token, _, _ = issue_auth_tokens(self.user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = client.get(self.url)

        self.assertEqual(response.status_code, 401)
