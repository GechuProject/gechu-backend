import logging
from typing import cast

from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.auth_utils import set_access_token_cookie, set_csrf_cookie, set_refresh_token_cookie
from apps.core.exceptions.exception_handler import CustomAPIException
from apps.users.services import (
    build_discord_login_url,
    build_kakao_login_url,
    build_social_error_redirect_url,
    build_social_success_redirect_url,
    handle_discord_callback,
    handle_kakao_callback,
)

logger = logging.getLogger(__name__)


@extend_schema(
    summary="카카오 로그인",
    description="카카오 OAuth 인증 페이지로 리다이렉트합니다. CSRF 방어용 state 값을 생성하여 캐시에 저장합니다.",
    request=None,
    responses={
        302: OpenApiResponse(description="카카오 OAuth 인증 페이지로 리다이렉트"),
    },
    tags=["auth"],
)
class KakaoLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> HttpResponseRedirect:
        login_url = build_kakao_login_url()
        return redirect(login_url)


class SocialCallbackAPIView(APIView):
    permission_classes = [AllowAny]

    def handle_callback(self, *, code: str, state: str) -> dict[str, object]:
        raise NotImplementedError

    def get(self, request: Request) -> HttpResponseRedirect:
        code = request.query_params.get("code", "")
        state = request.query_params.get("state", "")

        try:
            result = self.handle_callback(code=code, state=state)
            response = redirect(build_social_success_redirect_url(is_new_user=bool(result["is_new_user"])))
            set_access_token_cookie(
                response=response,
                access_token=str(result["access_token"]),
                expires_in=cast(int, result["expires_in"]),
            )
            set_refresh_token_cookie(response=response, refresh_token=str(result["refresh_token"]))
            set_csrf_cookie(request=request, response=response)
            return response

        except CustomAPIException as e:
            detail = cast(dict[str, str], e.detail)
            return redirect(
                build_social_error_redirect_url(
                    error=detail["code"],
                    error_description=detail["message"],
                )
            )

        except Exception:
            logger.exception("OAuth 콜백 처리 중 예상치 못한 오류 발생")
            return redirect(
                build_social_error_redirect_url(
                    error="SERVER_ERROR",
                    error_description="서버 오류가 발생했습니다.",
                )
            )


@extend_schema(
    summary="카카오 로그인 콜백 처리",
    description=(
        "카카오 OAuth 인증 후 호출되는 콜백 엔드포인트입니다.\n\n"
        "**성공 시** `{FRONTEND_DOMAIN}/auth/callback?is_new_user=true|false` 로 리다이렉트하며, "
        "`access_token`과 `refresh_token`을 HttpOnly 쿠키로 설정하고, `csrftoken` 쿠키를 함께 발급합니다.\n\n"
        "**실패 시** `{FRONTEND_DOMAIN}/auth/callback?error={코드}&error_description={메시지}` 로 리다이렉트합니다."
    ),
    request=None,
    parameters=[
        OpenApiParameter(
            name="code",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="카카오 OAuth 인증 코드",
        ),
        OpenApiParameter(
            name="state",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="CSRF 방어용 state 값(로그인 요청 시 발급)",
        ),
    ],
    responses={
        302: OpenApiResponse(
            description=(
                "성공: ?is_new_user=true|false + Set-Cookie: access_token, refresh_token (HttpOnly), csrftoken\n"
                "실패: ?error={에러코드}&error_description={메시지}"
            )
        ),
    },
    tags=["auth"],
)
class KakaoCallbackAPIView(SocialCallbackAPIView):
    def handle_callback(self, *, code: str, state: str) -> dict[str, object]:
        return handle_kakao_callback(code=code, state=state)


@extend_schema(
    summary="디스코드 로그인",
    description="디스코드 OAuth 인증 페이지로 리다이렉트합니다. CSRF 방어용 state 값을 생성하여 캐시에 저장합니다.",
    request=None,
    responses={
        302: OpenApiResponse(description="디스코드 OAuth 인증 페이지로 리다이렉트"),
    },
    tags=["auth"],
)
class DiscordLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> HttpResponseRedirect:
        login_url = build_discord_login_url()
        return redirect(login_url)


@extend_schema(
    summary="디스코드 로그인 콜백 처리",
    description=(
        "디스코드 OAuth 인증 후 호출되는 콜백 엔드포인트입니다.\n\n"
        "**성공 시** `{FRONTEND_DOMAIN}/auth/callback?is_new_user=true|false` 로 리다이렉트하며, "
        "`access_token`과 `refresh_token`을 HttpOnly 쿠키로 설정하고, `csrftoken` 쿠키를 함께 발급합니다.\n\n"
        "**실패 시** `{FRONTEND_DOMAIN}/auth/callback?error={코드}&error_description={메시지}` 로 리다이렉트합니다."
    ),
    request=None,
    parameters=[
        OpenApiParameter(
            name="code",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="디스코드 OAuth 인증 코드",
        ),
        OpenApiParameter(
            name="state",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="CSRF 방어용 state 값(로그인 요청 시 발급)",
        ),
    ],
    responses={
        302: OpenApiResponse(
            description=(
                "성공: ?is_new_user=true|false + Set-Cookie: access_token, refresh_token (HttpOnly), csrftoken\n"
                "실패: ?error={에러코드}&error_description={메시지}"
            )
        ),
    },
    tags=["auth"],
)
class DiscordCallbackAPIView(SocialCallbackAPIView):
    def handle_callback(self, *, code: str, state: str) -> dict[str, object]:
        return handle_discord_callback(code=code, state=state)
