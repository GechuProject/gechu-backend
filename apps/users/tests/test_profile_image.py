import datetime
import io
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.core.auth_test_utils import authenticate_client_with_cookies, make_cookie_client
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase


def make_image_file(width: int = 100, height: int = 100, fmt: str = "PNG") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buffer, format=fmt)
    buffer.seek(0)
    content_type = "image/png" if fmt == "PNG" else "image/jpeg"
    ext = fmt.lower()
    return SimpleUploadedFile(f"avatar.{ext}", buffer.read(), content_type=content_type)


@override_settings(
    AWS_S3_REGION_NAME="ap-northeast-2",
    AWS_STORAGE_BUCKET_NAME="test-bucket",
    AWS_S3_PUBLIC_BASE_URL="https://cdn.example.com",
)
class UserProfileImageAPITest(FastTestCase):
    def setUp(self) -> None:
        self.client: APIClient = make_cookie_client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="profile@example.com",
            password="Passw0rd!",
            nickname="profileuser",
            birth_date=datetime.date(1999, 1, 1),
        )
        self.url = reverse("users-me-profile-image")

    def test_upload_profile_image_returns_profile_img_url(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)
        mock_s3_client = MagicMock()

        with override_settings(S3_CLIENT=mock_s3_client):
            response = self.client.put(
                self.url,
                {"image": make_image_file()},
                format="multipart",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["profile_img_url"].startswith("https://cdn.example.com/images/profile/"))
        self.assertTrue(response.json()["profile_img_url"].endswith(".webp"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_img_url, response.json()["profile_img_url"])
        mock_s3_client.put_object.assert_called_once()
        _, kwargs = mock_s3_client.put_object.call_args
        self.assertEqual(kwargs["Bucket"], "test-bucket")
        self.assertEqual(kwargs["ContentType"], "image/webp")

    def test_upload_profile_image_resizes_large_image(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)
        mock_s3_client = MagicMock()

        captured: dict[str, bytes] = {}

        def capture_put(**kwargs: object) -> None:
            captured["body"] = kwargs["Body"]  # type: ignore[assignment]

        mock_s3_client.put_object.side_effect = capture_put

        with override_settings(S3_CLIENT=mock_s3_client):
            self.client.put(self.url, {"image": make_image_file(1000, 1000)}, format="multipart")

        img = Image.open(io.BytesIO(captured["body"]))
        self.assertLessEqual(img.width, 512)
        self.assertLessEqual(img.height, 512)

    def test_upload_profile_image_deletes_old_image(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)
        self.user.profile_img_url = f"https://cdn.example.com/images/profile/{self.user.id}/old.webp"
        self.user.save(update_fields=["profile_img_url"])
        mock_s3_client = MagicMock()

        with override_settings(S3_CLIENT=mock_s3_client):
            self.client.put(self.url, {"image": make_image_file()}, format="multipart")

        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=f"images/profile/{self.user.id}/old.webp",
        )

    def test_upload_profile_image_returns_401_when_not_authenticated(self) -> None:
        response = self.client.put(self.url, {"image": make_image_file()}, format="multipart")
        self.assertEqual(response.status_code, 401)

    def test_upload_profile_image_returns_400_for_invalid_content_type(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)
        gif_file = SimpleUploadedFile("avatar.gif", b"GIF89a", content_type="image/gif")

        response = self.client.put(self.url, {"image": gif_file}, format="multipart")

        self.assertEqual(response.status_code, 400)

    def test_upload_profile_image_returns_400_for_large_file(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)

        with patch("apps.users.services.user_me_service.PROFILE_IMAGE_MAX_SIZE_BYTES", 1):
            response = self.client.put(self.url, {"image": make_image_file()}, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.FILE_TOO_LARGE.name)

    def test_upload_profile_image_returns_401_when_user_is_deleted(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)
        self.user.deleted_at = timezone.now()
        self.user.is_active = False
        self.user.save(update_fields=["deleted_at", "is_active"])

        response = self.client.put(self.url, {"image": make_image_file()}, format="multipart")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], ErrorMessages.ACCOUNT_DEACTIVATED.name)

    def test_delete_profile_image_clears_profile_url(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)
        self.user.profile_img_url = f"https://cdn.example.com/images/profile/{self.user.id}/existing.webp"
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
            Key=f"images/profile/{self.user.id}/existing.webp",
        )

    def test_delete_profile_image_without_existing_image_returns_none(self) -> None:
        authenticate_client_with_cookies(self.client, self.user)
        mock_s3_client = MagicMock()

        with override_settings(S3_CLIENT=mock_s3_client):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["profile_img_url"])
        mock_s3_client.delete_object.assert_not_called()
