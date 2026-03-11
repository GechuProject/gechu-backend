from __future__ import annotations

import secrets
from datetime import date

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User

EMAIL_CODE_TTL_SECONDS = 300
EMAIL_CODE_COOLDOWN_SECONDS = 60


def get_active_user_or_deactivated(user: User) -> User:
    if user.deleted_at is not None or not user.is_active:
        raise CustomAPIException(ErrorMessages.ACCOUNT_DEACTIVATED)
    return user


def send_signup_email_code(email: str) -> int:
    if User.objects.filter(email=email).exists():
        raise CustomAPIException(ErrorMessages.EMAIL_ALREADY_EXISTS)

    cooldown_key = f"email_code_cooldown:{email}"
    if cache.get(cooldown_key):
        raise CustomAPIException(ErrorMessages.TOO_MANY_REQUESTS)

    code = f"{secrets.randbelow(1000000):06d}"
    cache.set(cooldown_key, True, timeout=EMAIL_CODE_COOLDOWN_SECONDS)
    cache.set(f"email_code:{email}", code, timeout=EMAIL_CODE_TTL_SECONDS)
    send_mail(
        subject="[Gechu] 이메일 인증 코드",
        message=f"인증 코드: {code}\n이 코드는 {EMAIL_CODE_TTL_SECONDS // 60}분 동안 유효합니다.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    return EMAIL_CODE_TTL_SECONDS


def signup_user(*, email: str, code: str, password: str, nickname: str, birth_date: date) -> User:
    if User.objects.filter(email=email).exists():
        raise CustomAPIException(ErrorMessages.EMAIL_ALREADY_EXISTS)

    saved_code = cache.get(f"email_code:{email}")
    if saved_code is None:
        raise CustomAPIException(ErrorMessages.CODE_EXPIRED)
    if str(saved_code) != code:
        raise CustomAPIException(ErrorMessages.INVALID_CODE)

    try:
        validate_password(password)
    except DjangoValidationError as err:
        raise CustomAPIException(ErrorMessages.VALIDATION_ERROR) from err

    user = User.objects.create_user(
        email=email,
        password=password,
        nickname=nickname,
        birth_date=birth_date,
    )
    cache.delete(f"email_code:{email}")
    return user


def authenticate_user(*, email: str, password: str) -> User:
    user = User.objects.filter(email=email).first()
    if user is None:
        raise CustomAPIException(ErrorMessages.INVALID_CREDENTIALS)

    get_active_user_or_deactivated(user)

    if not user.check_password(password):
        raise CustomAPIException(ErrorMessages.INVALID_CREDENTIALS)

    return user


def issue_auth_tokens(user: User) -> tuple[str, str, int]:
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    return str(access), str(refresh), int(access.lifetime.total_seconds())


def logout_user(refresh_token: str | None) -> None:
    if not refresh_token:
        raise CustomAPIException(ErrorMessages.REFRESH_TOKEN_MISSING)

    try:
        refresh = RefreshToken(refresh_token)  # type: ignore[arg-type]
        refresh.blacklist()
    except TokenError as err:
        raise CustomAPIException(ErrorMessages.INVALID_REFRESH_TOKEN) from err


def refresh_access_token(refresh_token: str | None) -> tuple[str, int]:
    if not refresh_token:
        raise CustomAPIException(ErrorMessages.REFRESH_TOKEN_MISSING)

    try:
        refresh = RefreshToken(refresh_token)  # type: ignore[arg-type]
        user_id = refresh.payload.get("user_id")
        if user_id is None:
            raise CustomAPIException(ErrorMessages.INVALID_REFRESH_TOKEN)

        user = User.objects.filter(id=int(user_id)).first()
        if user is None:
            raise CustomAPIException(ErrorMessages.ACCOUNT_DEACTIVATED)
        get_active_user_or_deactivated(user)

        access = refresh.access_token
    except TokenError as err:
        message = str(err)
        if "expired" in message.lower():
            raise CustomAPIException(ErrorMessages.REFRESH_TOKEN_EXPIRED) from err
        raise CustomAPIException(ErrorMessages.INVALID_REFRESH_TOKEN) from err

    return str(access), int(access.lifetime.total_seconds())
