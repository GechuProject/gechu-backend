import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.serializers.auth import (
    EmailCodeSendRequestSerializer,
    LoginSerializer,
    SignupRequestSerializer,
)


@extend_schema(
    summary="회원가입",
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
    summary="이메일 인증 코드 발송",
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

        code = f"{secrets.randbelow(1000000):06d}"
        cache.set(cooldown_key, True, timeout=self.COOLDOWN_SECONDS)
        cache.set(f"email_code:{email}", code, timeout=self.CODE_TTL_SECONDS)
        send_mail(
            subject="[Gechu] 이메일 인증 코드",
            message=(f"인증 코드: {code}\n이 코드는 {self.CODE_TTL_SECONDS // 60}분 동안 유효합니다."),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return Response(
            {"message": "인증 코드가 발송되었습니다.", "expires_in": self.CODE_TTL_SECONDS},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    summary="로그인",
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="LoginSuccessResponse",
                fields={
                    "access_token": serializers.CharField(),
                    "token_type": serializers.CharField(),
                    "expires_in": serializers.IntegerField(),
                },
            )
        )
    },
    tags=["auth"],
)
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        response = Response(
            {
                "access_token": str(access),
                "token_type": "Bearer",
                "expires_in": int(access.lifetime.total_seconds()),
            },
            status=status.HTTP_200_OK,
        )
        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            samesite="Lax",
        )
        return response


@extend_schema(
    summary="로그아웃",
    request=None,
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="LogoutSuccessResponse",
                fields={
                    "message": serializers.CharField(),
                },
            )
        )
    },
    tags=["auth"],
)
class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            raise CustomAPIException(ErrorMessages.REFRESH_TOKEN_MISSING)

        try:
            refresh = RefreshToken(refresh_token)  # type: ignore[arg-type]
            refresh.blacklist()
        except TokenError as err:
            raise CustomAPIException(ErrorMessages.INVALID_REFRESH_TOKEN) from err

        response = Response(
            {"message": "로그아웃 되었습니다."},
            status=status.HTTP_200_OK,
        )
        response.delete_cookie("refresh_token")
        return response


@extend_schema(
    summary="액세스 토큰 재발급",
    request=None,
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name="RefreshSuccessResponse",
                fields={
                    "access_token": serializers.CharField(),
                    "token_type": serializers.CharField(),
                    "expires_in": serializers.IntegerField(),
                },
            )
        )
    },
    tags=["auth"],
)
class RefreshAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            raise CustomAPIException(ErrorMessages.REFRESH_TOKEN_MISSING)

        try:
            refresh = RefreshToken(refresh_token)  # type: ignore[arg-type]
            User = get_user_model()
            user_id = refresh.payload.get("user_id")
            if user_id is None:
                raise CustomAPIException(ErrorMessages.INVALID_REFRESH_TOKEN)

            user = User.objects.filter(id=int(user_id)).first()

            if user is None or user.deleted_at is not None or user.is_active is False:
                raise CustomAPIException(ErrorMessages.ACCOUNT_DEACTIVATED)
            access = refresh.access_token
        except TokenError as err:
            message = str(err)
            if "expired" in message.lower():
                raise CustomAPIException(ErrorMessages.REFRESH_TOKEN_EXPIRED) from err
            raise CustomAPIException(ErrorMessages.INVALID_REFRESH_TOKEN) from err

        return Response(
            {
                "access_token": str(access),
                "token_type": "Bearer",
                "expires_in": int(access.lifetime.total_seconds()),
            },
            status=status.HTTP_200_OK,
        )
