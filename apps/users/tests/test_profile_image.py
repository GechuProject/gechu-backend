import datetime
import io
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models import UserProfileImage


def make_image_file(width: int = 100, height: int = 100, fmt: str = "PNG") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buffer, format=fmt)
    buffer.seek(0)
    content_type = "image/png" if fmt == "PNG" else "image/jpeg"
    ext = fmt.lower()
    return SimpleUploadedFile(f"avatar.{ext}", buffer.read(), content_type=content_type)


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

    def test_upload_profile_image_returns_profile_img_url(self) -> None:
        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            self.url,
            {"image": make_image_file()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/v1/users/profile-images/", response.json()["profile_img_url"])

        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_img_url, response.json()["profile_img_url"])
        profile_image = UserProfileImage.objects.get(user=self.user)
        self.assertEqual(profile_image.content_type, "image/webp")

    def test_upload_profile_image_resizes_large_image(self) -> None:
        self.client.force_authenticate(user=self.user)
        self.client.put(self.url, {"image": make_image_file(1000, 1000)}, format="multipart")

        profile_image = UserProfileImage.objects.get(user=self.user)
        img = Image.open(io.BytesIO(bytes(profile_image.image_data)))
        self.assertLessEqual(img.width, 256)
        self.assertLessEqual(img.height, 256)

    def test_upload_profile_image_overwrites_existing_stored_image(self) -> None:
        self.client.force_authenticate(user=self.user)
        first_response = self.client.put(self.url, {"image": make_image_file()}, format="multipart")
        first_url = first_response.json()["profile_img_url"]
        self.client.put(self.url, {"image": make_image_file(fmt="JPEG")}, format="multipart")

        self.assertEqual(UserProfileImage.objects.filter(user=self.user).count(), 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_img_url, first_url)

    def test_upload_profile_image_returns_401_when_not_authenticated(self) -> None:
        response = self.client.put(self.url, {"image": make_image_file()}, format="multipart")
        self.assertEqual(response.status_code, 401)

    def test_upload_profile_image_returns_400_for_invalid_content_type(self) -> None:
        self.client.force_authenticate(user=self.user)
        gif_file = SimpleUploadedFile("avatar.gif", b"GIF89a", content_type="image/gif")

        response = self.client.put(self.url, {"image": gif_file}, format="multipart")

        self.assertEqual(response.status_code, 400)

    def test_upload_profile_image_returns_400_for_large_file(self) -> None:
        self.client.force_authenticate(user=self.user)

        with patch("apps.users.services.user_me_service.PROFILE_IMAGE_MAX_SIZE_BYTES", 1):
            response = self.client.put(self.url, {"image": make_image_file()}, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], ErrorMessages.FILE_TOO_LARGE.name)

    def test_upload_profile_image_returns_404_when_user_is_deleted(self) -> None:
        self.user.deleted_at = timezone.now()
        self.user.save(update_fields=["deleted_at"])
        self.client.force_authenticate(user=self.user)

        response = self.client.put(self.url, {"image": make_image_file()}, format="multipart")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], ErrorMessages.USER_NOT_FOUND.name)

    def test_delete_profile_image_clears_profile_url(self) -> None:
        self.client.force_authenticate(user=self.user)
        self.client.put(self.url, {"image": make_image_file()}, format="multipart")
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["profile_img_url"])

        self.user.refresh_from_db()
        self.assertIsNone(self.user.profile_img_url)
        self.assertFalse(UserProfileImage.objects.filter(user=self.user).exists())

    def test_delete_profile_image_without_existing_image_returns_none(self) -> None:
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["profile_img_url"])

    def test_profile_image_content_returns_stored_image(self) -> None:
        self.client.force_authenticate(user=self.user)
        self.client.put(self.url, {"image": make_image_file()}, format="multipart")
        profile_image = UserProfileImage.objects.get(user=self.user)
        content_url = reverse("users-profile-image-content", kwargs={"public_id": profile_image.public_id})

        content_response = self.client.get(content_url)

        self.assertEqual(content_response.status_code, 200)
        self.assertEqual(content_response["Content-Type"], "image/webp")
        self.assertEqual(bytes(content_response.content), bytes(profile_image.image_data))

    def test_profile_image_content_returns_404_when_missing(self) -> None:
        response = self.client.get(reverse("users-profile-image-content", kwargs={"public_id": uuid.UUID(int=0)}))

        self.assertEqual(response.status_code, 404)
