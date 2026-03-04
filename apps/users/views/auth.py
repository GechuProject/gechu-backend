from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
import random
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from django.utils import timezone


class SignupAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        password = request.data.get("password")
        nickname = request.data.get("nickname")
        birth_date = request.data.get("birth_date")

        if not all([email, code, password, nickname, birth_date]):
            return Response(
                {"status_code": 400, "code": "VALIDATION_ERROR", "message": "필수 입력값이 누락되었습니다."},
                status=400,
            )
        try:
            EmailValidator()(email)
        except ValidationError:
            return Response(
                {"status_code": 400, "code": "VALIDATION_ERROR", "message": "이메일 형식이 올바르지 않습니다."},
                status=400,
            )
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            return Response(
                {"status_code": 409, "code": "EMAIL_ALREADY_EXISTS", "message": "이미 가입된 이메일입니다."},
                status=409,
            )
        saved_code = cache.get(f"email_code:{email}")
        if not saved_code:
            return Response(
                {"status_code": 400, "code": "CODE_EXPIRED", "message": "인증 코드가 만료되었습니다."},
                status=400,
            )

        if str(saved_code) != str(code):
            return Response(
                {"status_code": 400, "code": "INVALID_CODE", "message": "인증 코드가 올바르지 않습니다."},
                status=400,
            )
        return Response({"message": "검증 완료(유저 생성은 추후 연결)"}, status=200
        #     {
        #         "id": user.id,
        #         "email": user.email,
        #         "nickname": user.nickname,
        #         "birth_date": str(user.birth_date),
        #         "created_at": user.created_at.isoformat().replace("+00:00", "Z") if getattr(user, "created_at",
        #                                                                                     None) else None,
        #     },
        #     status=201,
        )

class EmailCodeSendAPIView(APIView):
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"status_code": 400, "code": "VALIDATION_ERROR", "message": "email은 필수입니다."},
                status=400,
            )
        try:
            EmailValidator()(email)
        except ValidationError:
            return Response(
                {"status_code": 400, "code": "VALIDATION_ERROR", "message": "이메일 형식이 올바르지 않습니다."},
                status=400,
            )
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            return Response(
                {"status_code": 409, "code": "EMAIL_ALREADY_EXISTS", "message": "이미 가입된 이메일입니다."},
                status=409,
            )
        cooldown_key = f"email_code_cooldown:{email}"
        if cache.get(cooldown_key):
            return Response(
                {"status_code": 429, "code": "TOO_MANY_REQUESTS", "message": "잠시 후 다시 시도해주세요."},
                status=429,
            )
        cache.set(cooldown_key, True, timeout=60)

        code = f"{random.randint(0, 999999):06d}"
        cache.set(f"email_code:{email}", code, timeout=300)

        return Response({"message": "인증 코드가 발송되었습니다.", "expires_in": 300})