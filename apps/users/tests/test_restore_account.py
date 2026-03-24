import datetime

from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.users.models.user import User
from apps.users.services.auth_service import issue_auth_tokens


class AccountRestoreAPITestCase(FastTestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/auth/restore/"
        self.user = User.objects.create_user(
            email="restore@example.com",
            nickname="restore-user",
            birth_date=datetime.date(1999, 1, 1),
            password="Passw0rd!",
        )

    def test_restore_account_success(self) -> None:
        self.user.deleted_at = timezone.now() - datetime.timedelta(days=3)
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])

        response = self.client.post(
            self.url,
            {"email": "restore@example.com", "password": "Passw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "계정이 복구되었습니다."})
        self.user.refresh_from_db()
        self.assertIsNone(self.user.deleted_at)
        self.assertTrue(self.user.is_active)

    def test_restore_account_returns_400_when_account_not_deleted(self) -> None:
        response = self.client.post(
            self.url,
            {"email": "restore@example.com", "password": "Passw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.ACCOUNT_NOT_DELETED.name)

    def test_restore_account_returns_400_when_restore_window_expired(self) -> None:
        self.user.deleted_at = timezone.now() - datetime.timedelta(days=8)
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])

        response = self.client.post(
            self.url,
            {"email": "restore@example.com", "password": "Passw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.ACCOUNT_RESTORE_EXPIRED.name)

    def test_restore_account_returns_401_for_invalid_password(self) -> None:
        self.user.deleted_at = timezone.now() - datetime.timedelta(days=3)
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])

        response = self.client.post(
            self.url,
            {"email": "restore@example.com", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], ErrorMessages.INVALID_CREDENTIALS.name)

    def test_restore_account_blacklists_existing_refresh_tokens(self) -> None:
        issue_auth_tokens(self.user)
        self.user.deleted_at = timezone.now() - datetime.timedelta(days=3)
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])

        response = self.client.post(
            self.url,
            {"email": "restore@example.com", "password": "Passw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        outstanding_tokens = OutstandingToken.objects.filter(user=self.user)
        self.assertEqual(
            BlacklistedToken.objects.filter(token__in=outstanding_tokens).count(),
            outstanding_tokens.count(),
        )
