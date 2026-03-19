from typing import cast
from urllib.parse import urljoin

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.users.serializers.social_auth import SocialCallbackRequestSerializer
from apps.users.services import (
    build_discord_login_url,
    build_kakao_login_url,
    handle_discord_callback,
    handle_kakao_callback,
)


def _resolve_social_redirect_url(request: Request, *, is_new_user: bool) -> str:
    frontend_base_url = getattr(settings, "FRONTEND_BASE_URL", None)
    frontend_domain = getattr(settings, "FRONTEND_DOMAIN", None)
    social_redirect_url = getattr(settings, "FRONTEND_SOCIAL_REDIRECT_URL", None)
    social_success_url = getattr(settings, "SOCIAL_LOGIN_SUCCESS_URL", None)
    social_onboarding_url = getattr(settings, "SOCIAL_LOGIN_ONBOARDING_URL", None)

    base_url = frontend_base_url or frontend_domain or social_redirect_url or request.build_absolute_uri("/")
    success_url = social_success_url or social_redirect_url or base_url
    onboarding_url = social_onboarding_url or urljoin(base_url.rstrip("/") + "/", "onboarding/")
    return onboarding_url if is_new_user else success_url


@extend_schema(
    summary="카카오 로그인",
    request=None,
    responses={
        302: OpenApiResponse(description="Redirect to Kakao OAuth"),
        500: ErrorResponseSerializer,
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

    def build_success_response(
        self,
        request: Request,
        *,
        result: dict[str, object],
    ) -> HttpResponseRedirect:
        refresh_token = cast(str, result.pop("refresh_token"))
        is_new_user = cast(bool, result["is_new_user"])
        redirect_url = _resolve_social_redirect_url(request, is_new_user=is_new_user)
        response = redirect(redirect_url)
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            samesite="Lax",
        )
        return response

    def get(self, request: Request) -> Response | HttpResponseRedirect:
        serializer = SocialCallbackRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        result = self.handle_callback(**serializer.validated_data)
        return self.build_success_response(request, result=result)


@extend_schema(
    summary="카카오 로그인 콜백 처리",
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
            description="카카오 OAuth state 값",
        ),
    ],
    responses={
        302: OpenApiResponse(description="Redirect to frontend after Kakao login"),
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="INVALID_STATE, OAUTH_CALLBACK_ERROR 또는 query parameter 검증 오류",
        ),
    },
    tags=["auth"],
)
class KakaoCallbackAPIView(SocialCallbackAPIView):
    def handle_callback(self, *, code: str, state: str) -> dict[str, object]:
        return handle_kakao_callback(code=code, state=state)


@extend_schema(
    summary="디스코드 로그인",
    request=None,
    responses={
        302: OpenApiResponse(description="Redirect to Discord OAuth"),
        500: ErrorResponseSerializer,
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
            description="디스코드 OAuth state 값",
        ),
    ],
    responses={
        302: OpenApiResponse(description="Redirect to frontend after Discord login"),
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="INVALID_STATE, DISCORD_OAUTH_CALLBACK_ERROR 또는 query parameter 검증 오류",
        ),
    },
    tags=["auth"],
)
class DiscordCallbackAPIView(SocialCallbackAPIView):
    def handle_callback(self, *, code: str, state: str) -> dict[str, object]:
        return handle_discord_callback(code=code, state=state)
