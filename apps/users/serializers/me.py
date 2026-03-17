from rest_framework import serializers

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


class UserMeUpdateRequestSerializer(serializers.Serializer[dict[str, object]]):
    nickname = serializers.CharField(required=False, max_length=30)
    birth_date = serializers.DateField(required=False)
    new_password = serializers.CharField(required=False, write_only=True)


class UserPasswordVerifyRequestSerializer(serializers.Serializer[dict[str, object]]):
    password = serializers.CharField(write_only=True)


class UserPasswordChangeRequestSerializer(serializers.Serializer[dict[str, object]]):
    new_password = serializers.CharField(write_only=True)


class UserProfileImageUploadRequestSerializer(serializers.Serializer[dict[str, object]]):
    file_name = serializers.CharField()
    content_type = serializers.CharField()
    file_size = serializers.IntegerField(min_value=1)


class UserProfileImageUploadResponseSerializer(serializers.Serializer[dict[str, object]]):
    upload_url = serializers.URLField()
    profile_img_url = serializers.URLField(allow_null=True)
    expires_in = serializers.IntegerField()


class UserProfileImageResponseSerializer(serializers.Serializer[dict[str, object]]):
    profile_img_url = serializers.URLField(allow_null=True)


class UserMeDeleteResponseSerializer(serializers.Serializer[dict[str, object]]):
    message = serializers.CharField()
