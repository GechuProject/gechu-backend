import datetime
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages


@override_settings(
    AWS_S3_REGION_NAME="ap-northeast-2",
    AWS_STORAGE_BUCKET_NAME="test-bucket",
    AWS_S3_PUBLIC_BASE_URL="https://cdn.example.com",
    AWS_S3_PRESIGNED_URL_EXPIRES_IN=3600,
)
class UserProfileImageAPITest(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="profile@example.com",
            password="Passw0rd!",
            nickname="profileuser",
            birth_date=datetime.date(1999, 1, 1),
        )
        self.url = reverse("users-me-profile-image")

    def test_create_profile_image_upload_url_returns_presigned_url(self) -> None:
        self.client.force_authenticate(user=self.user)
        mock_s3_client = MagicMock()
        mock_s3_client.generate_presigned_url.return_value = "https://signed.example.com/upload"

        with override_settings(S3_CLIENT=mock_s3_client):
            response = self.client.put(
                self.url,
                {
                    "file_name": "avatar.png",
                    "content_type": "image/png",
                    "file_size": 1024,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["upload_url"], "https://signed.example.com/upload")
        self.assertEqual(response.json()["expires_in"], 3600)
        self.assertTrue(response.json()["profile_img_url"].startswith("https://cdn.example.com/profile-images/"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_img_url, response.json()["profile_img_url"])
        mock_s3_client.generate_presigned_url.assert_called_once()
        _, kwargs = mock_s3_client.generate_presigned_url.call_args
        self.assertEqual(kwargs["ClientMethod"], "put_object")
        self.assertEqual(kwargs["Params"]["Bucket"], "test-bucket")
        self.assertEqual(kwargs["Params"]["ContentType"], "image/png")
        self.assertEqual(kwargs["ExpiresIn"], 3600)

    def test_create_profile_image_upload_url_returns_401_when_not_authenticated(self) -> None:
        response = self.client.put(
            self.url,
            {
                "file_name": "avatar.png",
                "content_type": "image/png",
                "file_size": 1024,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_create_profile_image_upload_url_returns_400_for_invalid_extension(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            self.url,
            {
                "file_name": "avatar.txt",
                "content_type": "text/plain",
                "file_size": 1024,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.INVALID_FILE_TYPE.name)

    def test_create_profile_image_upload_url_returns_400_for_large_file(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            self.url,
            {
                "file_name": "avatar.png",
                "content_type": "image/png",
                "file_size": 5 * 1024 * 1024 + 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.FILE_TOO_LARGE.name)

    def test_create_profile_image_upload_url_returns_404_when_user_is_deleted(self) -> None:
        self.user.deleted_at = timezone.now()
        self.user.save(update_fields=["deleted_at"])
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            self.url,
            {
                "file_name": "avatar.png",
                "content_type": "image/png",
                "file_size": 1024,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], ErrorMessages.USER_NOT_FOUND.name)

    def test_delete_profile_image_clears_profile_url(self) -> None:
        self.client.force_authenticate(user=self.user)
        self.user.profile_img_url = f"https://cdn.example.com/profile-images/{self.user.id}/existing.png"
        self.user.save(update_fields=["profile_img_url"])
        mock_s3_client = MagicMock()

        with override_settings(S3_CLIENT=mock_s3_client):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["profile_img_url"])

        self.user.refresh_from_db()
        self.assertIsNone(self.user.profile_img_url)
        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=f"profile-images/{self.user.id}/existing.png",
        )

    def test_delete_profile_image_without_existing_image_returns_none(self) -> None:
        self.client.force_authenticate(user=self.user)
        mock_s3_client = MagicMock()

        with override_settings(S3_CLIENT=mock_s3_client):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["profile_img_url"])
        mock_s3_client.delete_object.assert_not_called()
