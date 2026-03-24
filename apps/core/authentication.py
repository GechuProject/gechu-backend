from typing import Any, cast

from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import AuthUser, JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import Token

from apps.core.auth_utils import enforce_csrf
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User


class CookieAuthAPIException(APIException):
    def __init__(self, error: ErrorMessages) -> None:
        self.status_code = error.status_code
        self.detail = cast(
            dict[str, Any],
            {
                "status_code": error.status_code,
                "code": error.name,
                "message": error.message,
            },
        )


class CookieJWTAuthentication(JWTAuthentication):
    """
    access_token HttpOnly cookie에서만 인증 정보를 읽습니다.
    쿠키 기반 인증 시 CSRF 검사를 강제합니다.
    """

    def authenticate(self, request: Request) -> tuple[AuthUser, Token] | None:
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None

        enforce_csrf(request)
        try:
            validated_token = self.get_validated_token(raw_token.encode())
        except InvalidToken as exc:
            if "expired" in str(exc).lower():
                raise CookieAuthAPIException(ErrorMessages.TOKEN_EXPIRED) from exc
            raise CookieAuthAPIException(ErrorMessages.UNAUTHORIZED) from exc

        return cast(AuthUser, self._get_active_user(validated_token)), validated_token

    def _get_active_user(self, validated_token: Token) -> User:
        user_id = validated_token.get(api_settings.USER_ID_CLAIM)
        if user_id is None:
            raise CookieAuthAPIException(ErrorMessages.UNAUTHORIZED)

        try:
            user = self.user_model.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except self.user_model.DoesNotExist as exc:
            raise CookieAuthAPIException(ErrorMessages.UNAUTHORIZED) from exc
        except AuthenticationFailed as exc:
            raise CookieAuthAPIException(ErrorMessages.UNAUTHORIZED) from exc

        if not isinstance(user, User):
            raise CookieAuthAPIException(ErrorMessages.UNAUTHORIZED)

        if not user.is_active:
            raise CookieAuthAPIException(ErrorMessages.ACCOUNT_DEACTIVATED)

        return user
