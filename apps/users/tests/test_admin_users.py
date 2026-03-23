import datetime

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.core.auth_test_utils import authenticate_client_with_cookies, make_cookie_client
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.recommendations.models import RecommendationJob
from apps.users.services.auth_service import issue_auth_tokens

User = get_user_model()


class AdminUserAPITestCase(FastTestCase):
    def setUp(self) -> None:
        self.client: APIClient = make_cookie_client()
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
        self.dashboard_url = reverse("admin-dashboard-summary")

    def test_admin_dashboard_summary_returns_counts_for_admin(self) -> None:
        authenticate_client_with_cookies(self.client, self.admin_user)

        failed_job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.user,
            status=RecommendationJob.Status.FAILED,
        )
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.SIMILARITY_REBUILD,
            status=RecommendationJob.Status.PENDING,
        )
        yesterday = timezone.now() - datetime.timedelta(days=1)
        RecommendationJob.objects.filter(id=failed_job.id).update(created_at=yesterday)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_users"], 3)
        self.assertEqual(response.json()["active_users"], 3)
        self.assertEqual(response.json()["recommendation_jobs_today"], 1)
        self.assertEqual(response.json()["failed_jobs"], 1)

    def test_admin_dashboard_summary_returns_403_for_non_admin(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], ErrorMessages.FORBIDDEN.name)

    def test_admin_dashboard_summary_returns_401_when_not_authenticated(self) -> None:
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 401)

    def test_admin_user_list_returns_paginated_users_for_admin(self) -> None:
        authenticate_client_with_cookies(self.client, self.admin_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.json())
        self.assertIn("results", response.json())
        self.assertTrue(any(item["email"] == "user@example.com" for item in response.json()["results"]))

    def test_admin_user_list_returns_403_for_non_admin(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], ErrorMessages.FORBIDDEN.name)

    def test_admin_user_detail_returns_user_data_for_admin(self) -> None:
        authenticate_client_with_cookies(self.client, self.admin_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "user@example.com")
        self.assertEqual(response.json()["nickname"], "normal-user")

    def test_admin_user_detail_returns_404_when_user_does_not_exist(self) -> None:
        authenticate_client_with_cookies(self.client, self.admin_user)

        response = self.client.get(reverse("admin-user-detail", args=[999999]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], ErrorMessages.USER_NOT_FOUND.name)

    def test_admin_user_status_update_changes_is_active(self) -> None:
        authenticate_client_with_cookies(self.client, self.admin_user)

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

    def test_admin_user_status_update_reactivates_deleted_user_and_clears_deleted_at(self) -> None:
        authenticate_client_with_cookies(self.client, self.admin_user)
        self.user.deleted_at = timezone.now()
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])

        response = self.client.patch(
            self.detail_url,
            {
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_active"])
        self.assertIsNone(response.json()["deleted_at"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIsNone(self.user.deleted_at)

    def test_admin_user_status_update_blacklists_existing_refresh_tokens(self) -> None:
        authenticate_client_with_cookies(self.client, self.admin_user)
        issue_auth_tokens(self.user)
        issue_auth_tokens(self.user)

        response = self.client.patch(
            self.detail_url,
            {
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        outstanding_tokens = OutstandingToken.objects.filter(user=self.user)
        self.assertEqual(
            BlacklistedToken.objects.filter(token__in=outstanding_tokens).count(),
            outstanding_tokens.count(),
        )

    def test_admin_user_status_update_returns_403_for_non_admin(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)

        response = self.client.patch(
            self.detail_url,
            {
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], ErrorMessages.FORBIDDEN.name)
