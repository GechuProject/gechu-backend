from __future__ import annotations

import io
from datetime import date
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models import UserProfileImage
from apps.users.models.user import User
from apps.users.services.auth_service import get_active_user_or_deactivated, revoke_all_refresh_tokens

PROFILE_IMAGE_MAX_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_PROFILE_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_PROFILE_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
PROFILE_IMAGE_MAX_DIMENSION = (256, 256)
PROFILE_IMAGE_QUALITY = 75


def get_user_me(user: User) -> User:
    if user.deleted_at is not None:
        raise CustomAPIException(ErrorMessages.USER_NOT_FOUND)
    return user


def update_user_me(
    user: User,
    *,
    nickname: str | None = None,
    birth_date: date | None = None,
    new_password: str | None = None,
) -> User:
    user = get_user_me(user)
    update_fields: list[str] = []

    if nickname is not None:
        queryset = User.objects.filter(nickname=nickname).exclude(pk=user.pk)
        if queryset.exists():
            raise CustomAPIException(ErrorMessages.NICKNAME_ALREADY_EXISTS)
        user.nickname = nickname
        update_fields.append("nickname")

    if birth_date is not None:
        user.birth_date = birth_date
        update_fields.append("birth_date")

    if new_password is not None:
        get_active_user_or_deactivated(user)

        if user.social_accounts.exists() and not user.has_usable_password():
            raise CustomAPIException(ErrorMessages.SOCIAL_USER_ONLY)

        try:
            validate_password(new_password)
        except DjangoValidationError as err:
            raise CustomAPIException(ErrorMessages.VALIDATION_ERROR) from err

        user.set_password(new_password)
        update_fields.append("password")

    if update_fields:
        user.save(update_fields=update_fields + ["updated_at"])
        if new_password is not None:
            revoke_all_refresh_tokens(user)

    return user


def delete_user_me(user: User) -> None:
    user = get_user_me(user)
    user.deleted_at = timezone.now()
    user.is_active = False
    user.save(update_fields=["deleted_at", "is_active", "updated_at"])


def verify_user_password(user: User, *, password: str) -> None:
    user = get_user_me(user)
    get_active_user_or_deactivated(user)

    if user.social_accounts.exists() and not user.has_usable_password():
        raise CustomAPIException(ErrorMessages.SOCIAL_USER_ONLY)

    if not user.check_password(password):
        raise CustomAPIException(ErrorMessages.INVALID_PASSWORD)


def change_user_password(user: User, *, new_password: str) -> None:
    user = get_user_me(user)
    get_active_user_or_deactivated(user)

    if user.social_accounts.exists() and not user.has_usable_password():
        raise CustomAPIException(ErrorMessages.SOCIAL_USER_ONLY)

    try:
        validate_password(new_password)
    except DjangoValidationError as err:
        raise CustomAPIException(ErrorMessages.VALIDATION_ERROR) from err

    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    revoke_all_refresh_tokens(user)


def _resize_image(image_file: Any, max_size: tuple[int, int] = PROFILE_IMAGE_MAX_DIMENSION) -> bytes:
    try:
        from PIL import Image
    except ImportError as err:
        raise CustomAPIException(ErrorMessages.SERVER_ERROR) from err

    opened = Image.open(image_file)
    converted = opened.convert("RGB") if opened.mode not in ("RGB", "RGBA") else opened
    converted.thumbnail(max_size, Image.Resampling.LANCZOS)

    output = io.BytesIO()
    converted.save(output, format="WEBP", quality=PROFILE_IMAGE_QUALITY, method=6)
    return output.getvalue()


def _build_profile_image_url(*, base_url: str, public_id: Any) -> str:
    relative_path = reverse("users-profile-image-content", kwargs={"public_id": public_id})
    return f"{base_url.rstrip('/')}{relative_path}"


def upload_user_profile_image(
    user: User,
    *,
    image_file: Any,
    base_url: str,
) -> dict[str, object]:
    user = get_user_me(user)

    content_type = getattr(image_file, "content_type", "")
    if content_type not in ALLOWED_PROFILE_IMAGE_CONTENT_TYPES:
        raise CustomAPIException(ErrorMessages.INVALID_FILE_TYPE)

    file_name = getattr(image_file, "name", "")
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension not in ALLOWED_PROFILE_IMAGE_EXTENSIONS:
        raise CustomAPIException(ErrorMessages.INVALID_FILE_TYPE)

    if image_file.size > PROFILE_IMAGE_MAX_SIZE_BYTES:
        raise CustomAPIException(ErrorMessages.FILE_TOO_LARGE)

    resized_bytes = _resize_image(image_file)
    profile_image, _ = UserProfileImage.objects.get_or_create(user=user)
    profile_image.image_data = resized_bytes
    profile_image.content_type = "image/webp"
    profile_image.save(update_fields=["image_data", "content_type", "updated_at"])

    profile_img_url = _build_profile_image_url(base_url=base_url, public_id=profile_image.public_id)
    user.profile_img_url = profile_img_url
    user.save(update_fields=["profile_img_url", "updated_at"])

    return {"profile_img_url": profile_img_url}


def delete_user_profile_image(user: User) -> dict[str, object]:
    user = get_user_me(user)
    UserProfileImage.objects.filter(user=user).delete()

    user.profile_img_url = None
    user.save(update_fields=["profile_img_url", "updated_at"])

    return {"profile_img_url": None}


def get_profile_image_content(*, public_id: Any) -> UserProfileImage:
    profile_image = UserProfileImage.objects.filter(public_id=public_id).select_related("user").first()
    if profile_image is None or profile_image.user.deleted_at is not None:
        raise CustomAPIException(ErrorMessages.USER_NOT_FOUND)
    return profile_image
