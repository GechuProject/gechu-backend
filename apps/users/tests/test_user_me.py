import datetime
from typing import cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.core.auth_test_utils import authenticate_client_with_cookies, make_cookie_client
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.users.models.social_user import SocialUser
from apps.users.tasks import purge_soft_deleted_users


class UserMeRetrieveAPITest(FastTestCase):
    def setUp(self) -> None:
        self.client = make_cookie_client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="me@example.com",
            password="Passw0rd!",
            nickname="gamer123",
            birth_date=datetime.date(1999, 1, 1),
        )

    def test_get_me_returns_current_user_info(self) -> None:
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)

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
        self.assertFalse(drf_res.data["is_social_user"])
        self.assertIsNone(drf_res.data["social_provider"])
        self.assertTrue(drf_res.data["created_at"])

    def test_get_me_returns_social_user_info_for_social_only_account(self) -> None:
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        SocialUser.objects.create(
            user=self.user,
            provider=SocialUser.Provider.KAKAO,
            provider_uid="kakao-social-only",
        )

        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)

        res = client.get("/api/v1/users/me/")

        drf_res = cast(Response, res)

        self.assertEqual(drf_res.status_code, 200)
        self.assertTrue(drf_res.data["is_social_user"])
        self.assertEqual(drf_res.data["social_provider"], SocialUser.Provider.KAKAO)

    def test_get_me_returns_401_when_not_authenticated(self) -> None:
        noauth_res = self.client.get("/api/v1/users/me/")
        self.assertEqual(noauth_res.status_code, 401)

    def test_get_me_returns_401_when_user_is_deleted(self) -> None:
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)
        self.user.deleted_at = timezone.now()
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])
        res = client.get("/api/v1/users/me/")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], ErrorMessages.ACCOUNT_DEACTIVATED.name)

    def test_patch_me_updates_user_info(self) -> None:
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)
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
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)

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

    def test_patch_me_changes_password_when_new_password_is_provided(self) -> None:
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)

        res = client.patch(
            "/api/v1/users/me/",
            {
                "new_password": "NewPassw0rd!",
            },
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassw0rd!"))

    def test_patch_me_returns_400_for_invalid_new_password(self) -> None:
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)

        res = client.patch(
            "/api/v1/users/me/",
            {
                "new_password": "123",
            },
            format="json",
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], ErrorMessages.VALIDATION_ERROR.name)

    def test_patch_me_returns_400_for_social_only_user_with_new_password(self) -> None:
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        SocialUser.objects.create(
            user=self.user,
            provider=SocialUser.Provider.KAKAO,
            provider_uid="kakao-social-only",
        )

        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)

        res = client.patch(
            "/api/v1/users/me/",
            {
                "new_password": "NewPassw0rd!",
            },
            format="json",
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], ErrorMessages.SOCIAL_USER_ONLY.name)

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
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)
        res = client.patch(
            "/api/v1/users/me/",
            {
                "nickname": "duplicated",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 409)

    def test_patch_me_returns_400_when_birth_date_is_invalid(self) -> None:
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)

        res = client.patch(
            "/api/v1/users/me/",
            {
                "birth_date": "invalid-date",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_delete_me_soft_deletes_user(self) -> None:
        client = make_cookie_client()
        authenticate_client_with_cookies(client, self.user)

        res = client.delete("/api/v1/users/me/")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"message": "계정이 삭제되었습니다."})
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.deleted_at)
        self.assertFalse(self.user.is_active)
        outstanding_tokens = OutstandingToken.objects.filter(user=self.user)
        self.assertEqual(
            BlacklistedToken.objects.filter(token__in=outstanding_tokens).count(),
            outstanding_tokens.count(),
        )

    def test_delete_me_returns_401_when_not_authenticated(self) -> None:
        res = self.client.delete("/api/v1/users/me/")

        self.assertEqual(res.status_code, 401)

    def test_purge_soft_deleted_users_deletes_users_after_7_days(self) -> None:
        self.user.deleted_at = timezone.now() - datetime.timedelta(days=8)
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])

        deleted_count = purge_soft_deleted_users()

        self.assertEqual(deleted_count, 1)
        self.assertFalse(get_user_model().objects.filter(id=self.user.id).exists())

    def test_purge_soft_deleted_users_keeps_recently_deleted_users(self) -> None:
        self.user.deleted_at = timezone.now() - datetime.timedelta(days=6)
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])

        deleted_count = purge_soft_deleted_users()

        self.assertEqual(deleted_count, 0)
        self.assertTrue(get_user_model().objects.filter(id=self.user.id).exists())
