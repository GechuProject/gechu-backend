from rest_framework import serializers

from apps.users.models.user import User


class SignupRequestSerializer(serializers.Serializer[dict[str, object]]):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)
    password = serializers.CharField(write_only=True)
    nickname = serializers.CharField()
    birth_date = serializers.DateField()


class SignupResponseSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nickname",
            "birth_date",
            "created_at",
        ]


class EmailCodeSendRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    email = serializers.EmailField(required=True)
    purpose = serializers.ChoiceField(choices=["signup", "password_reset"], required=True)


class EmailCodeSendResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    message = serializers.CharField()
    expires_in = serializers.IntegerField()


class LoginRequestSerializer(serializers.Serializer[dict[str, object]]):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True)


class AccountRestoreRequestSerializer(serializers.Serializer[dict[str, object]]):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer[dict[str, object]]):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(write_only=True)


class TokenResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    access_token = serializers.CharField()
    token_type = serializers.CharField()
    expires_in = serializers.IntegerField()


class MessageResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    message = serializers.CharField()


class CSRFTokenResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    csrf_token = serializers.CharField()


class AuthMeResponseSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "is_active",
            "is_adult_verified",
        ]
