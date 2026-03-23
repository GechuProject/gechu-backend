from __future__ import annotations

import io
import uuid
from datetime import date
from typing import Any

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User
from apps.users.services.auth_service import get_active_user_or_deactivated, revoke_all_refresh_tokens

PROFILE_IMAGE_MAX_SIZE_BYTES = 5 * 1024 * 1024
PROFILE_IMAGE_UPLOAD_DIR = "images/profile"
ALLOWED_PROFILE_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_PROFILE_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


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


def _get_s3_client() -> Any:
    s3_client = getattr(settings, "S3_CLIENT", None)
    if s3_client is not None:
        return s3_client

    try:
        import boto3
    except ImportError as err:
        raise CustomAPIException(ErrorMessages.SERVER_ERROR) from err

    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION_NAME,
    )


def _ensure_profile_image_storage_config() -> None:
    required_settings = (
        settings.AWS_STORAGE_BUCKET_NAME,
        settings.AWS_S3_PUBLIC_BASE_URL,
        settings.AWS_S3_REGION_NAME,
    )
    if not all(required_settings):
        raise CustomAPIException(ErrorMessages.SERVER_ERROR)


def _build_profile_image_url(object_key: str) -> str:
    public_base_url = settings.AWS_S3_PUBLIC_BASE_URL
    if public_base_url is None:
        raise CustomAPIException(ErrorMessages.SERVER_ERROR)
    return f"{public_base_url.rstrip('/')}/{object_key}"


def _get_profile_image_object_key(profile_img_url: str | None) -> str | None:
    if not profile_img_url or not settings.AWS_S3_PUBLIC_BASE_URL:
        return None

    prefix = f"{settings.AWS_S3_PUBLIC_BASE_URL.rstrip('/')}/"
    if profile_img_url.startswith(prefix):
        return profile_img_url.removeprefix(prefix)
    return None


def _resize_image(image_file: Any, max_size: tuple[int, int] = (512, 512)) -> bytes:
    try:
        from PIL import Image
    except ImportError as err:
        raise CustomAPIException(ErrorMessages.SERVER_ERROR) from err

    opened = Image.open(image_file)
    converted = opened.convert("RGB") if opened.mode not in ("RGB", "RGBA") else opened
    converted.thumbnail(max_size, Image.Resampling.LANCZOS)

    output = io.BytesIO()
    converted.save(output, format="WEBP", quality=85)
    return output.getvalue()


def upload_user_profile_image(
    user: User,
    *,
    image_file: Any,
) -> dict[str, object]:
    user = get_user_me(user)
    _ensure_profile_image_storage_config()

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

    old_key = _get_profile_image_object_key(user.profile_img_url)

    object_key = f"{PROFILE_IMAGE_UPLOAD_DIR}/{user.id}/{uuid.uuid4().hex}.webp"
    _get_s3_client().put_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=object_key,
        Body=resized_bytes,
        ContentType="image/webp",
    )

    if old_key is not None:
        _get_s3_client().delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=old_key)

    profile_img_url = _build_profile_image_url(object_key)
    user.profile_img_url = profile_img_url
    user.save(update_fields=["profile_img_url", "updated_at"])

    return {"profile_img_url": profile_img_url}


def delete_user_profile_image(user: User) -> dict[str, object]:
    user = get_user_me(user)
    _ensure_profile_image_storage_config()

    object_key = _get_profile_image_object_key(user.profile_img_url)
    if object_key is not None:
        _get_s3_client().delete_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=object_key,
        )

    user.profile_img_url = None
    user.save(update_fields=["profile_img_url", "updated_at"])

    return {"profile_img_url": None}
