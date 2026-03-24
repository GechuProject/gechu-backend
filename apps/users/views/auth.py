from typing import cast

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.auth_utils import (
    enforce_csrf,
    expire_auth_cookies,
    set_access_token_cookie,
    set_csrf_cookie,
    set_refresh_token_cookie,
)
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.users.models.user import User
from apps.users.serializers.auth import (
    AccountRestoreRequestSerializer,
    AuthMeResponseSerializer,
    CSRFTokenResponseSerializer,
    EmailCodeSendRequestSerializer,
    EmailCodeSendResponseSerializer,
    LoginRequestSerializer,
    MessageResponseSerializer,
    PasswordResetRequestSerializer,
    SignupRequestSerializer,
    SignupResponseSerializer,
)
from apps.users.services import (
    authenticate_user,
    get_active_user_or_deactivated,
    issue_auth_tokens,
    logout_user,
    refresh_access_token,
    reset_user_password,
    restore_user_account,
    send_email_code,
    signup_user,
)


@extend_schema(
    summary="회원가입",
    request=SignupRequestSerializer,
    responses={
        201: SignupResponseSerializer,
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="VALIDATION_ERROR, INVALID_CODE, CODE_EXPIRED",
        ),
        409: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="EMAIL_ALREADY_EXISTS, NICKNAME_ALREADY_EXISTS",
        ),
    },
    tags=["auth"],
)
class SignupAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = SignupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = signup_user(**serializer.validated_data)
        return Response(SignupResponseSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="이메일 인증 코드 발송",
    request=EmailCodeSendRequestSerializer,
    responses={
        201: EmailCodeSendResponseSerializer,
        400: OpenApiResponse(response=ErrorResponseSerializer, description="VALIDATION_ERROR"),
        409: OpenApiResponse(response=ErrorResponseSerializer, description="EMAIL_ALREADY_EXISTS"),
        429: OpenApiResponse(response=ErrorResponseSerializer, description="TOO_MANY_REQUESTS"),
    },
    tags=["auth"],
)
class EmailCodeSendAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = EmailCodeSendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        expires_in = send_email_code(
            email=serializer.validated_data["email"],
            purpose=serializer.validated_data["purpose"],
        )
        response_serializer = EmailCodeSendResponseSerializer(
            {"message": "인증 코드가 발송되었습니다.", "expires_in": expires_in}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="CSRF 토큰 발급",
    request=None,
    responses={200: CSRFTokenResponseSerializer},
    tags=["auth"],
)
class AuthCSRFAPIView(APIView):
    authentication_classes: tuple[type[BaseAuthentication], ...] = ()
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        response = Response(status=status.HTTP_200_OK)
        csrf_token = set_csrf_cookie(request=request, response=response)
        response.data = CSRFTokenResponseSerializer({"csrf_token": csrf_token}).data
        return response


@extend_schema(
    summary="로그인",
    request=LoginRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=MessageResponseSerializer,
            description="Sets HttpOnly access_token and refresh_token cookies, and also issues a csrftoken cookie for subsequent unsafe requests.",
        ),
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="INVALID_CREDENTIALS, ACCOUNT_DEACTIVATED",
        ),
        403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
    },
    tags=["auth"],
)
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        enforce_csrf(request)

        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate_user(**serializer.validated_data)
        access_token, refresh_token, expires_in = issue_auth_tokens(user)

        response_serializer = MessageResponseSerializer({"message": "로그인 되었습니다."})
        response = Response(response_serializer.data, status=status.HTTP_200_OK)
        set_access_token_cookie(response=response, access_token=access_token, expires_in=expires_in)
        set_refresh_token_cookie(response=response, refresh_token=refresh_token)
        set_csrf_cookie(request=request, response=response)
        return response


@extend_schema(
    summary="로그아웃",
    request=None,
    responses={
        200: MessageResponseSerializer,
        400: OpenApiResponse(response=ErrorResponseSerializer, description="REFRESH_TOKEN_MISSING"),
        401: OpenApiResponse(response=ErrorResponseSerializer, description="INVALID_REFRESH_TOKEN"),
        403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
    },
    tags=["auth"],
)
class LogoutAPIView(APIView):
    authentication_classes: tuple[type[BaseAuthentication], ...] = ()
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        logout_user(request.COOKIES.get("refresh_token"))

        response_serializer = MessageResponseSerializer({"message": "로그아웃 되었습니다."})
        response = Response(response_serializer.data, status=status.HTTP_200_OK)
        expire_auth_cookies(response=response)
        return response


@extend_schema(
    summary="액세스 토큰 재발급",
    request=None,
    responses={
        200: OpenApiResponse(
            response=MessageResponseSerializer,
            description="Refreshes the session, rotates the refresh token, updates the HttpOnly access_token and refresh_token cookies, and reissues the csrftoken cookie.",
        ),
        400: OpenApiResponse(response=ErrorResponseSerializer, description="REFRESH_TOKEN_MISSING"),
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="INVALID_REFRESH_TOKEN, REFRESH_TOKEN_EXPIRED, ACCOUNT_DEACTIVATED",
        ),
        403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
    },
    tags=["auth"],
)
class RefreshAPIView(APIView):
    authentication_classes: tuple[type[BaseAuthentication], ...] = ()
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        access_token, refresh_token, expires_in = refresh_access_token(request.COOKIES.get("refresh_token"))

        response_serializer = MessageResponseSerializer({"message": "액세스 토큰이 갱신되었습니다."})
        response = Response(response_serializer.data, status=status.HTTP_200_OK)
        set_access_token_cookie(response=response, access_token=access_token, expires_in=expires_in)
        set_refresh_token_cookie(response=response, refresh_token=refresh_token)
        set_csrf_cookie(request=request, response=response)
        return response


@extend_schema(
    summary="비밀번호 재설정",
    request=PasswordResetRequestSerializer,
    responses={200: MessageResponseSerializer},
    tags=["auth"],
)
class PasswordResetAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reset_user_password(**serializer.validated_data)
        response_serializer = MessageResponseSerializer({"message": "비밀번호가 재설정되었습니다."})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    summary="탈퇴 계정 복구",
    request=AccountRestoreRequestSerializer,
    responses={200: MessageResponseSerializer},
    tags=["auth"],
)
class AccountRestoreAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = AccountRestoreRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        restore_user_account(**serializer.validated_data)
        response_serializer = MessageResponseSerializer({"message": "계정이 복구되었습니다."})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    summary="현재 인증 사용자 조회",
    request=None,
    responses={
        200: AuthMeResponseSerializer,
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="UNAUTHORIZED, TOKEN_EXPIRED, ACCOUNT_DEACTIVATED",
        ),
    },
    tags=["auth"],
)
class AuthMeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = get_active_user_or_deactivated(cast(User, request.user))
        return Response(AuthMeResponseSerializer(user).data, status=status.HTTP_200_OK)
