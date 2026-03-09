from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User


class SignupRequestSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)
    password = serializers.CharField(write_only=True)
    nickname = serializers.CharField()
    birth_date = serializers.DateField()

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email=value).exists():
            raise CustomAPIException(ErrorMessages.EMAIL_ALREADY_EXISTS)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        email = attrs["email"]
        code = attrs["code"]

        key = f"email_code:{email}"
        saved_code = cache.get(key)

        if saved_code is None:
            raise CustomAPIException(ErrorMessages.CODE_EXPIRED)

        if str(saved_code) != code:
            raise CustomAPIException(ErrorMessages.INVALID_CODE)

        return attrs

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as err:
            raise CustomAPIException(ErrorMessages.VALIDATION_ERROR) from err
        return value


class EmailCodeSendRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    email = serializers.EmailField(required=True)


class LoginSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        email = attrs["email"]
        password = attrs["password"]

        user = User.objects.filter(email=email).first()
        if user is None:
            raise CustomAPIException(ErrorMessages.INVALID_CREDENTIALS)

        if user.deleted_at is not None or user.is_active is False:
            raise CustomAPIException(ErrorMessages.ACCOUNT_DEACTIVATED)

        if not user.check_password(password):
            raise CustomAPIException(ErrorMessages.INVALID_CREDENTIALS)

        attrs["user"] = user
        return attrs
