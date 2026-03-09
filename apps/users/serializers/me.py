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
            "adult_verification_expires_at",
            "created_at",
        ]
