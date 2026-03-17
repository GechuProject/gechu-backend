from __future__ import annotations

from django.db.models import QuerySet

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User


def list_admin_users() -> QuerySet[User]:
    return User.objects.order_by("-created_at")


def get_admin_user(*, user_id: int) -> User:
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise CustomAPIException(ErrorMessages.USER_NOT_FOUND) from None


def update_admin_user_status(*, user_id: int, is_active: bool) -> User:
    user = get_admin_user(user_id=user_id)
    user.is_active = is_active
    user.save(update_fields=["is_active", "updated_at"])
    return user
