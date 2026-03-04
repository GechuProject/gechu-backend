from random import randint

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from apps.users.serializers.auth import EmailCodeSendRequestSerializer

@extend_schema(
    request=EmailCodeSendRequestSerializer,
    responses={200: None},
)
class EmailCodeSendAPIView(APIView):
    permission_classes = [AllowAny]

    CODE_TTL_SECONDS = 300
    COOLDOWN_SECONDS = 60

    def post(self, request):
        email = request.data.get("email")

        # 1) 필수값 검증
        if not email:
            return Response(
                {"error_detail": "email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) 이메일 형식 검증
        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"error_detail": "invalid email format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3) 이미 가입된 이메일 체크 (409)
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            return Response(
                {"error_detail": "email already exists"},
                status=status.HTTP_409_CONFLICT,
            )

        code_key = f"email_code:{email}"
        cooldown_key = f"email_code_cooldown:{email}"

        # 4) 재요청 쿨다운 60초
        if cache.get(cooldown_key):
            return Response(
                {"error_detail": "too many requests"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # 5) 6자리 인증코드 생성
        code = f"{randint(0, 999999):06d}"

        # 6) Redis 저장 (5분) + 쿨다운(60초)
        cache.set(code_key, code, timeout=self.CODE_TTL_SECONDS)
        cache.set(cooldown_key, 1, timeout=self.COOLDOWN_SECONDS)

        # TODO: 실제 이메일 발송 연동 (현재는 Redis 저장까지만)
        return Response(
            {"detail": "인증 코드가 발송되었습니다.", "expires_in": self.CODE_TTL_SECONDS},
            status=status.HTTP_200_OK,
        )