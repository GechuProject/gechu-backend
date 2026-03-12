import datetime

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.social_user import SocialUser
from apps.users.models.user import User


class PasswordResetAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="reset@example.com",
            nickname="resetuser",
            birth_date=datetime.date(1997, 10, 2),
            password="OldPass1234!",
        )
        self.url = "/api/v1/auth/password/reset/"

    def test_password_reset_success(self) -> None:
        cache.set("email_code:reset@example.com", "123456", timeout=300)

        response = self.client.post(
            self.url,
            {
                "email": "reset@example.com",
                "code": "123456",
                "new_password": "NewPass1234!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "비밀번호가 재설정되었습니다.")

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass1234!"))
        self.assertIsNone(cache.get("email_code:reset@example.com"))

    def test_password_reset_invalid_code(self) -> None:
        cache.set("email_code:reset@example.com", "123456", timeout=300)

        response = self.client.post(
            self.url,
            {
                "email": "reset@example.com",
                "code": "654321",
                "new_password": "NewPass1234!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.INVALID_CODE.name)

    def test_password_reset_expired_code(self) -> None:
        response = self.client.post(
            self.url,
            {
                "email": "reset@example.com",
                "code": "123456",
                "new_password": "NewPass1234!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.INVALID_CODE.name)

    def test_password_reset_social_user_only(self) -> None:
        social_user = User.objects.create_user(
            email="social@example.com",
            nickname="socialuser",
            birth_date=datetime.date(1998, 1, 1),
            password=None,
        )
        SocialUser.objects.create(
            user=social_user,
            provider=SocialUser.Provider.KAKAO,
            provider_uid="kakao-123",
        )
        cache.set("email_code:social@example.com", "123456", timeout=300)

        response = self.client.post(
            self.url,
            {
                "email": "social@example.com",
                "code": "123456",
                "new_password": "NewPass1234!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.SOCIAL_USER_ONLY.name)

    def test_password_reset_invalid_password(self) -> None:
        cache.set("email_code:reset@example.com", "123456", timeout=300)

        response = self.client.post(
            self.url,
            {
                "email": "reset@example.com",
                "code": "123456",
                "new_password": "123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.VALIDATION_ERROR.name)

    def test_password_reset_blacklists_existing_refresh_tokens(self) -> None:
        cache.set("email_code:reset@example.com", "123456", timeout=300)
        RefreshToken.for_user(self.user)
        RefreshToken.for_user(self.user)

        response = self.client.post(
            self.url,
            {
                "email": "reset@example.com",
                "code": "123456",
                "new_password": "NewPass1234!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        outstanding_tokens = OutstandingToken.objects.filter(user=self.user)
        self.assertEqual(
            BlacklistedToken.objects.filter(token__in=outstanding_tokens).count(), outstanding_tokens.count()
        )
