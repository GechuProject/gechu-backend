from random import randint

from django.contrib.auth import get_user_model
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.auth import (
    EmailCodeSendRequestSerializer,
    SignupRequestSerializer,
)


@extend_schema(
    request=SignupRequestSerializer,
    responses={201: None},
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

        # 인증코드는 1회성: 회원가입 성공 후 삭제
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
)
class EmailCodeSendAPIView(APIView):
    permission_classes = [AllowAny]

    CODE_TTL_SECONDS = 300
    COOLDOWN_SECONDS = 60

    def post(self, request: Request) -> Response:
        serializer = EmailCodeSendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email: str = serializer.validated_data["email"]

        # 이미 가입된 이메일이면 코드 발급 불가
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            return Response(
                {"code": "EMAIL_ALREADY_EXISTS", "message": "이미 가입된 이메일입니다."},
                status=status.HTTP_409_CONFLICT,
            )

        cooldown_key = f"email_code_cooldown:{email}"
        if cache.get(cooldown_key):
            return Response(
                {"code": "TOO_MANY_REQUESTS", "message": "잠시 후 다시 시도해주세요."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        code = f"{randint(0, 999999):06d}"
        cache.set(cooldown_key, True, timeout=self.COOLDOWN_SECONDS)
        cache.set(f"email_code:{email}", code, timeout=self.CODE_TTL_SECONDS)

        # TODO: 실제 이메일 발송 연동 (현재는 Redis 저장까지만)
        return Response(
            {"message": "인증 코드가 발송되었습니다.", "expires_in": self.CODE_TTL_SECONDS},
            status=status.HTTP_201_CREATED,
        )