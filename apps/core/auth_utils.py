from datetime import timedelta
from typing import Any, Literal, TypedDict, cast

from django.conf import settings
from django.http.response import HttpResponseBase
from django.middleware.csrf import get_token
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import APIException
from rest_framework.request import Request

from apps.core.exceptions.exception_message import ErrorMessages


class AuthCookieOptions(TypedDict):
    httponly: bool
    samesite: Literal["None"]
    secure: bool


class CSRFCookieOptions(TypedDict):
    samesite: Literal["None"]
    secure: bool


AUTH_COOKIE_OPTIONS: AuthCookieOptions = {
    "httponly": True,
    "samesite": "None",
    "secure": True,
}

CSRF_COOKIE_OPTIONS: CSRFCookieOptions = {
    "samesite": "None",
    "secure": True,
}


class CSRFFailedAPIException(APIException):
    def __init__(self) -> None:
        self.status_code = ErrorMessages.CSRF_FAILED.status_code
        self.detail = cast(
            dict[str, Any],
            {
                "status_code": ErrorMessages.CSRF_FAILED.status_code,
                "code": ErrorMessages.CSRF_FAILED.name,
                "message": ErrorMessages.CSRF_FAILED.message,
            },
        )


def enforce_csrf(request: Request) -> None:
    check = CSRFCheck(request)  # type: ignore[arg-type]
    check.process_request(request)
    reason = check.process_view(request, lambda r: None, (), {})  # type: ignore[arg-type, return-value]
    if reason:
        raise CSRFFailedAPIException()


def set_access_token_cookie(*, response: HttpResponseBase, access_token: str, expires_in: int) -> None:
    response.set_cookie("access_token", value=access_token, max_age=expires_in, **AUTH_COOKIE_OPTIONS)


def set_refresh_token_cookie(*, response: HttpResponseBase, refresh_token: str) -> None:
    refresh_max_age = int(cast(timedelta, settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]).total_seconds())
    response.set_cookie("refresh_token", value=refresh_token, max_age=refresh_max_age, **AUTH_COOKIE_OPTIONS)


def set_csrf_cookie(*, request: Request, response: HttpResponseBase) -> str:
    csrf_token = get_token(request)
    response.set_cookie("csrftoken", value=csrf_token, **CSRF_COOKIE_OPTIONS)
    return csrf_token


def expire_auth_cookies(*, response: HttpResponseBase) -> None:
    response.set_cookie("refresh_token", value="", max_age=0, **AUTH_COOKIE_OPTIONS)
    response.set_cookie("access_token", value="", max_age=0, **AUTH_COOKIE_OPTIONS)
