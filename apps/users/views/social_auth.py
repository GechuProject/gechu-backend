from typing import cast

from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.users.serializers.social_auth import (
    SocialCallbackRequestSerializer,
    SocialLoginResponseSerializer,
)
from apps.users.services import build_kakao_login_url, handle_kakao_callback


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
        200: SocialLoginResponseSerializer,
        201: SocialLoginResponseSerializer,
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="INVALID_STATE, OAUTH_CALLBACK_ERROR 또는 query parameter 검증 오류",
        ),
    },
    tags=["auth"],
)
class KakaoCallbackAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        serializer = SocialCallbackRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        result = handle_kakao_callback(**serializer.validated_data)

        refresh_token = cast(str, result.pop("refresh_token"))
        is_new_user = result["is_new_user"]
        status_code = status.HTTP_201_CREATED if is_new_user else status.HTTP_200_OK

        response = Response(SocialLoginResponseSerializer(result).data, status=status_code)
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            samesite="Lax",
        )
        return response
