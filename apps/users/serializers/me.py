from typing import ClassVar

from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User


class UserMeResponseSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nickname",
            "birth_date",
            "profile_img_url",
            "is_adult_verified",
            "adult_verified_at",
            "is_active",
            "created_at",
        ]


class UserMeUpdateResponseSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nickname",
            "birth_date",
            "updated_at",
        ]


class UserMeUpdateRequestSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = [
            "nickname",
            "birth_date",
        ]
        extra_kwargs: ClassVar[dict[str, dict[str, list[object]]]] = {
            "nickname": {
                "validators": [],
            },
        }

    def validate_nickname(self, value: str) -> str:
        queryset = User.objects.filter(nickname=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise CustomAPIException(ErrorMessages.NICKNAME_ALREADY_EXISTS)
        return value
