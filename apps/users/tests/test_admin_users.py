import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages

User = get_user_model()


class AdminUserAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            nickname="admin-user",
            birth_date=datetime.date(1990, 1, 1),
            password="Admin1234!",
        )
        self.user = User.objects.create_user(
            email="user@example.com",
            nickname="normal-user",
            birth_date=datetime.date(1999, 1, 1),
            password="Passw0rd!",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            nickname="other-user",
            birth_date=datetime.date(1998, 1, 1),
            password="Passw0rd!",
        )
        self.list_url = reverse("admin-user-list")
        self.detail_url = reverse("admin-user-detail", args=[self.user.id])

    def test_admin_user_list_returns_paginated_users_for_admin(self) -> None:
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.json())
        self.assertIn("results", response.json())
        self.assertTrue(any(item["email"] == "user@example.com" for item in response.json()["results"]))

    def test_admin_user_list_returns_403_for_non_admin(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], ErrorMessages.FORBIDDEN.name)

    def test_admin_user_detail_returns_user_data_for_admin(self) -> None:
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "user@example.com")
        self.assertEqual(response.json()["nickname"], "normal-user")

    def test_admin_user_detail_returns_404_when_user_does_not_exist(self) -> None:
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(reverse("admin-user-detail", args=[999999]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], ErrorMessages.USER_NOT_FOUND.name)

    def test_admin_user_status_update_changes_is_active(self) -> None:
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.patch(
            self.detail_url,
            {
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_admin_user_status_update_returns_403_for_non_admin(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.detail_url,
            {
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], ErrorMessages.FORBIDDEN.name)
