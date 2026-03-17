from __future__ import annotations

from rest_framework import serializers

from apps.users.models.user import User


class AdminUserListItemSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nickname",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_adult_verified",
            "deleted_at",
            "created_at",
        ]


class AdminUserListResponseSerializer(serializers.Serializer[dict[str, object]]):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = AdminUserListItemSerializer(many=True)


class AdminUserDetailResponseSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nickname",
            "birth_date",
            "profile_img_url",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_adult_verified",
            "adult_verified_at",
            "adult_verification_expires_at",
            "deleted_at",
            "created_at",
            "updated_at",
        ]


class AdminUserStatusUpdateRequestSerializer(serializers.Serializer[dict[str, object]]):
    is_active = serializers.BooleanField()
