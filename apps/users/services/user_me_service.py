from __future__ import annotations

from datetime import date

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User
from apps.users.services.auth_service import get_active_user_or_deactivated


def get_user_me(user: User) -> User:
    if user.deleted_at is not None:
        raise CustomAPIException(ErrorMessages.USER_NOT_FOUND)
    return user


def update_user_me(user: User, *, nickname: str | None = None, birth_date: date | None = None) -> User:
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

    if update_fields:
        user.save(update_fields=update_fields + ["updated_at"])

    return user


def verify_user_password(user: User, *, password: str) -> None:
    user = get_user_me(user)
    get_active_user_or_deactivated(user)

    if user.social_accounts.exists() and not user.has_usable_password():
        raise CustomAPIException(ErrorMessages.SOCIAL_USER_ONLY)

    if not user.check_password(password):
        raise CustomAPIException(ErrorMessages.INVALID_PASSWORD)
