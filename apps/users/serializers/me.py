from rest_framework import serializers

from apps.users.models.user import User


class UserMeResponseSerializer(serializers.ModelSerializer[User]):
    is_social_user = serializers.SerializerMethodField()
    social_provider = serializers.SerializerMethodField()

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
            "is_social_user",
            "social_provider",
            "created_at",
        ]

    def get_is_social_user(self, obj: User) -> bool:
        return obj.social_accounts.exists() and not obj.has_usable_password()

    def get_social_provider(self, obj: User) -> str | None:
        social_account = obj.social_accounts.order_by("id").first()
        return social_account.provider if social_account is not None else None


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


class UserMeUpdateRequestSerializer(serializers.Serializer[dict[str, object]]):
    nickname = serializers.CharField(required=False, max_length=30)
    birth_date = serializers.DateField(required=False)
    new_password = serializers.CharField(required=False, write_only=True)


class UserPasswordVerifyRequestSerializer(serializers.Serializer[dict[str, object]]):
    password = serializers.CharField(write_only=True)


class UserProfileImageUploadRequestSerializer(serializers.Serializer[dict[str, object]]):
    image = serializers.ImageField()


class UserProfileImageResponseSerializer(serializers.Serializer[dict[str, object]]):
    profile_img_url = serializers.URLField(allow_null=True)


class UserMeDeleteResponseSerializer(serializers.Serializer[dict[str, object]]):
    message = serializers.CharField()
