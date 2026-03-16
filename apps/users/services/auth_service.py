from __future__ import annotations

import secrets
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User

EMAIL_CODE_TTL_SECONDS = 300
EMAIL_CODE_COOLDOWN_SECONDS = 60
EMAIL_CODE_VERIFY_MAX_ATTEMPTS = 5
EMAIL_CODE_VERIFY_BLOCK_SECONDS = 20 * 60
EMAIL_CODE_PURPOSE_SIGNUP = "signup"
EMAIL_CODE_PURPOSE_PASSWORD_RESET = "password_reset"


def _email_code_key(*, purpose: str, email: str) -> str:
    return f"email_code:{purpose}:{email}"


def _email_code_cooldown_key(*, purpose: str, email: str) -> str:
    return f"email_code_cooldown:{purpose}:{email}"


def _email_code_attempts_key(*, purpose: str, email: str) -> str:
    return f"email_code_attempts:{purpose}:{email}"


def _should_issue_email_code(*, email: str, purpose: str) -> bool:
    user_exists = User.objects.filter(email=email).exists()
    if purpose == EMAIL_CODE_PURPOSE_SIGNUP:
        return not user_exists
    return user_exists


def get_active_user_or_deactivated(user: User) -> User:
    if user.deleted_at is not None or not user.is_active:
        raise CustomAPIException(ErrorMessages.ACCOUNT_DEACTIVATED)
    return user


def send_email_code(*, email: str, purpose: str) -> int:
    cooldown_key = _email_code_cooldown_key(purpose=purpose, email=email)
    if cache.get(cooldown_key):
        raise CustomAPIException(ErrorMessages.TOO_MANY_REQUESTS)

    cache.set(cooldown_key, True, timeout=EMAIL_CODE_COOLDOWN_SECONDS)

    if _should_issue_email_code(email=email, purpose=purpose):
        code = f"{secrets.randbelow(1000000):06d}"
        cache.set(_email_code_key(purpose=purpose, email=email), code, timeout=EMAIL_CODE_TTL_SECONDS)
        cache.delete(_email_code_attempts_key(purpose=purpose, email=email))
        send_mail(
            subject="[Gechu] Email verification code",
            message=f"Verification code: {code}\nThis code is valid for {EMAIL_CODE_TTL_SECONDS // 60} minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

    return EMAIL_CODE_TTL_SECONDS


def signup_user(*, email: str, code: str, password: str, nickname: str, birth_date: date) -> User:
    if User.objects.filter(email=email).exists():
        raise CustomAPIException(ErrorMessages.EMAIL_ALREADY_EXISTS)
    if User.objects.filter(nickname=nickname).exists():
        raise CustomAPIException(ErrorMessages.NICKNAME_ALREADY_EXISTS)

    saved_code = cache.get(_email_code_key(purpose=EMAIL_CODE_PURPOSE_SIGNUP, email=email))
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
    cache.delete(_email_code_key(purpose=EMAIL_CODE_PURPOSE_SIGNUP, email=email))
    cache.delete(_email_code_attempts_key(purpose=EMAIL_CODE_PURPOSE_SIGNUP, email=email))
    return user


def authenticate_user(*, email: str, password: str) -> User:
    user = User.objects.filter(email=email).first()
    if user is None:
        raise CustomAPIException(ErrorMessages.INVALID_CREDENTIALS)

    get_active_user_or_deactivated(user)

    if not user.check_password(password):
        raise CustomAPIException(ErrorMessages.INVALID_CREDENTIALS)

    return user


def restore_user_account(*, email: str, password: str) -> None:
    with transaction.atomic():
        user = User.objects.select_for_update().filter(email=email).first()
        if user is None or not user.check_password(password):
            raise CustomAPIException(ErrorMessages.INVALID_CREDENTIALS)

        if user.deleted_at is None:
            raise CustomAPIException(ErrorMessages.ACCOUNT_NOT_DELETED)

        restore_deadline = user.deleted_at + timedelta(days=settings.ACCOUNT_DELETION_RETENTION_DAYS)
        if restore_deadline < timezone.now():
            raise CustomAPIException(ErrorMessages.ACCOUNT_RESTORE_EXPIRED)

        user.deleted_at = None
        user.is_active = True
        user.save(update_fields=["deleted_at", "is_active", "updated_at"])


def revoke_all_refresh_tokens(user: User) -> None:
    outstanding_tokens = OutstandingToken.objects.filter(user=user)
    for token in outstanding_tokens:
        BlacklistedToken.objects.get_or_create(token=token)


def reset_user_password(*, email: str, code: str, new_password: str) -> None:
    attempts_key = _email_code_attempts_key(purpose=EMAIL_CODE_PURPOSE_PASSWORD_RESET, email=email)
    failed_attempts = int(cache.get(attempts_key, 0))
    if failed_attempts >= EMAIL_CODE_VERIFY_MAX_ATTEMPTS:
        raise CustomAPIException(ErrorMessages.TOO_MANY_REQUESTS)

    saved_code = cache.get(_email_code_key(purpose=EMAIL_CODE_PURPOSE_PASSWORD_RESET, email=email))
    if saved_code is None or not secrets.compare_digest(str(saved_code), code):
        failed_attempts += 1
        cache.set(attempts_key, failed_attempts, timeout=EMAIL_CODE_VERIFY_BLOCK_SECONDS)
        if failed_attempts >= EMAIL_CODE_VERIFY_MAX_ATTEMPTS:
            cache.delete(_email_code_key(purpose=EMAIL_CODE_PURPOSE_PASSWORD_RESET, email=email))
        raise CustomAPIException(ErrorMessages.INVALID_CODE)

    user = User.objects.filter(email=email).first()
    if user is None:
        raise CustomAPIException(ErrorMessages.INVALID_CODE)

    if user.social_accounts.exists() and not user.has_usable_password():
        raise CustomAPIException(ErrorMessages.SOCIAL_USER_ONLY)

    try:
        validate_password(new_password)
    except DjangoValidationError as err:
        raise CustomAPIException(ErrorMessages.VALIDATION_ERROR) from err

    user.set_password(new_password)
    user.save(update_fields=["password"])
    revoke_all_refresh_tokens(user)
    cache.delete(_email_code_key(purpose=EMAIL_CODE_PURPOSE_PASSWORD_RESET, email=email))
    cache.delete(attempts_key)


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
            raise CustomAPIException(ErrorMessages.INVALID_REFRESH_TOKEN)
        get_active_user_or_deactivated(user)

        access = refresh.access_token
    except TokenError as err:
        message = str(err)
        if "expired" in message.lower():
            raise CustomAPIException(ErrorMessages.REFRESH_TOKEN_EXPIRED) from err
        raise CustomAPIException(ErrorMessages.INVALID_REFRESH_TOKEN) from err

    return str(access), int(access.lifetime.total_seconds())
