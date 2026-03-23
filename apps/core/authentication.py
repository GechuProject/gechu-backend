from rest_framework.request import Request
from rest_framework_simplejwt.authentication import AuthUser, JWTAuthentication
from rest_framework_simplejwt.tokens import Token

from apps.core.auth_utils import enforce_csrf


class CookieJWTAuthentication(JWTAuthentication):
    """
    Authorization header 우선, 없으면 access_token HttpOnly 쿠키에서 읽습니다.
    쿠키 기반 인증 시 CSRF 검사를 강제합니다.
    """

    def authenticate(self, request: Request) -> tuple[AuthUser, Token] | None:
        header_result = super().authenticate(request)
        if header_result is not None:
            return header_result  # type: ignore[return-value]

        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None

        enforce_csrf(request)
        validated_token = self.get_validated_token(raw_token.encode())
        return self.get_user(validated_token), validated_token  # type: ignore[return-value]
