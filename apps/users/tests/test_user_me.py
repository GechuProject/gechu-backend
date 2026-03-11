import datetime
from typing import cast

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient


class UserMeRetrieveAPITest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="me@example.com",
            password="Passw0rd!",
            nickname="gamer123",
            birth_date=datetime.date(1999, 1, 1),
        )

    def test_get_me_returns_current_user_info(self) -> None:
        client = APIClient()
        client.force_authenticate(user=self.user)

        res = client.get("/api/v1/users/me/")

        drf_res = cast(Response, res)

        self.assertEqual(drf_res.status_code, 200)
        self.assertEqual(drf_res.data["id"], self.user.id)
        self.assertEqual(drf_res.data["email"], self.user.email)
        self.assertEqual(drf_res.data["nickname"], self.user.nickname)
        self.assertEqual(drf_res.data["birth_date"], str(self.user.birth_date))
        self.assertEqual(drf_res.data["profile_img_url"], self.user.profile_img_url)
        self.assertEqual(drf_res.data["is_adult_verified"], self.user.is_adult_verified)
        self.assertEqual(drf_res.data["adult_verified_at"], self.user.adult_verified_at)
        self.assertEqual(drf_res.data["is_active"], self.user.is_active)
        self.assertTrue(drf_res.data["created_at"])

    def test_get_me_returns_401_when_not_authenticated(self) -> None:
        noauth_res = self.client.get("/api/v1/users/me/")
        self.assertEqual(noauth_res.status_code, 401)

    def test_get_me_returns_404_when_user_is_deleted(self) -> None:
        client = APIClient()
        client.force_authenticate(user=self.user)
        self.user.deleted_at = timezone.now()
        self.user.save(update_fields=["deleted_at"])
        res = client.get("/api/v1/users/me/")
        self.assertEqual(res.status_code, 404)

    def test_patch_me_updates_user_info(self) -> None:
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.patch(
            "/api/v1/users/me/",
            {
                "nickname": "updated123",
                "birth_date": "2000-02-02",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["nickname"], "updated123")
        self.assertEqual(res.data["birth_date"], "2000-02-02")
        self.assertTrue(res.data["updated_at"])

    def test_patch_me_updates_only_provided_fields(self) -> None:
        client = APIClient()
        client.force_authenticate(user=self.user)

        res = client.patch(
            "/api/v1/users/me/",
            {
                "nickname": "onlynickname",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["nickname"], "onlynickname")
        self.assertEqual(res.data["birth_date"], "1999-01-01")

    def test_patch_me_returns_401_when_not_authenticated(self) -> None:
        res = self.client.patch(
            "/api/v1/users/me/",
            {
                "nickname": "updated123",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 401)

    def test_patch_me_returns_409_when_nickname_already_exists(self) -> None:
        get_user_model().objects.create_user(
            email="other@example.com",
            password="Passw0rd!",
            nickname="duplicated",
            birth_date=datetime.date(1998, 1, 1),
        )
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.patch(
            "/api/v1/users/me/",
            {
                "nickname": "duplicated",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 409)

    def test_patch_me_returns_400_when_birth_date_is_invalid(self) -> None:
        client = APIClient()
        client.force_authenticate(user=self.user)

        res = client.patch(
            "/api/v1/users/me/",
            {
                "birth_date": "invalid-date",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)
