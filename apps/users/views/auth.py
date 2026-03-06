from random import randint

from django.contrib.auth import get_user_model
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.serializers.auth import (
    EmailCodeSendRequestSerializer,
    LoginSerializer,
    SignupRequestSerializer,
)


@extend_schema(
    request=SignupRequestSerializer,
    responses={201: None},
    tags=["auth"],
)
class SignupAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = SignupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        User = get_user_model()

        user = User.objects.create_user(
            email=data["email"],
            password=data["password"],
            nickname=data["nickname"],
            birth_date=data["birth_date"],
        )

        cache.delete(f"email_code:{data['email']}")

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "nickname": user.nickname,
                "birth_date": str(user.birth_date),
                "created_at": user.created_at.isoformat().replace("+00:00", "Z")
                if getattr(user, "created_at", None)
                else None,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    request=EmailCodeSendRequestSerializer,
    responses={201: None},
    tags=["auth"],
)
class EmailCodeSendAPIView(APIView):
    permission_classes = [AllowAny]

    CODE_TTL_SECONDS = 300
    COOLDOWN_SECONDS = 60

    def post(self, request: Request) -> Response:
        serializer = EmailCodeSendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email: str = serializer.validated_data["email"]

        User = get_user_model()
        if User.objects.filter(email=email).exists():
            raise CustomAPIException(ErrorMessages.EMAIL_ALREADY_EXISTS)

        cooldown_key = f"email_code_cooldown:{email}"
        if cache.get(cooldown_key):
            raise CustomAPIException(ErrorMessages.TOO_MANY_REQUESTS)

        code = f"{randint(0, 999999):06d}"
        cache.set(cooldown_key, True, timeout=self.COOLDOWN_SECONDS)
        cache.set(f"email_code:{email}", code, timeout=self.CODE_TTL_SECONDS)

        return Response(
            {"message": "인증 코드가 발송되었습니다.", "expires_in": self.CODE_TTL_SECONDS},
            status=status.HTTP_201_CREATED,
        )


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        return Response(
            {
                "access_token": str(access),
                "token_type": "Bearer",
                "expires_in": 3600,
            },
            status=status.HTTP_200_OK,
        )
