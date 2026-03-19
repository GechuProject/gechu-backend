from datetime import datetime
from typing import cast
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.users.models.user import User
from apps.users.serializers.adult_verification import (
    AdultVerificationCallbackRequestSerializer,
    AdultVerificationStatusResponseSerializer,
)
from apps.users.services.adult_verification_service import (
    complete_adult_verification,
    get_adult_verification_status,
    initiate_adult_verification,
)


def _append_query_params(url: str, **params: str) -> str:
    split_result = urlsplit(url)
    query_params = dict(parse_qsl(split_result.query, keep_blank_values=True))
    query_params.update(params)
    return urlunsplit(split_result._replace(query=urlencode(query_params)))


def _resolve_adult_verification_redirect_url(request: Request) -> str:
    frontend_base_url = getattr(settings, "FRONTEND_BASE_URL", None) or getattr(settings, "FRONTEND_DOMAIN", None)
    if isinstance(frontend_base_url, str) and frontend_base_url:
        return urljoin(frontend_base_url.rstrip("/") + "/", "auth/callback")
    return request.build_absolute_uri("/")


def _isoformat(value: object) -> str:
    return cast(datetime, value).isoformat()


@extend_schema(
    summary="Adult Verification Initiate",
    request=None,
    responses={
        302: OpenApiResponse(description="Redirect to Bbaton OAuth"),
        401: ErrorResponseSerializer,
    },
    tags=["users"],
)
class AdultVerificationInitiateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> HttpResponseRedirect:
        verification_url = initiate_adult_verification(user=cast(User, request.user))
        return redirect(verification_url)


@extend_schema(
    summary="Adult Verification Callback",
    request=None,
    parameters=[
        OpenApiParameter(
            name="code",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Bbaton OAuth authorization code",
        ),
        OpenApiParameter(
            name="state",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Bbaton OAuth state value",
        ),
    ],
    responses={
        302: OpenApiResponse(description="Redirect to frontend after adult verification"),
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="INVALID_STATE, ADULT_VERIFICATION_CALLBACK_ERROR, UNDERAGE, ALREADY_VERIFIED",
        ),
        409: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="VERIFICATION_ALREADY_USED",
        ),
    },
    tags=["users"],
)
class AdultVerificationCallbackAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response | HttpResponseRedirect:
        serializer = AdultVerificationCallbackRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        code = cast(str, serializer.validated_data["code"])
        state = cast(str, serializer.validated_data["state"])
        redirect_url = _resolve_adult_verification_redirect_url(request)

        try:
            result = complete_adult_verification(code=code, state=state)
        except CustomAPIException as error:
            error_detail = cast(dict[str, object], error.detail)
            return redirect(
                _append_query_params(
                    redirect_url,
                    error=cast(str, error_detail["code"]),
                    error_description=cast(str, error_detail["message"]),
                )
            )

        return redirect(
            _append_query_params(
                redirect_url,
                is_adult_verified=str(cast(bool, result["is_adult_verified"])).lower(),
                adult_verified_at=_isoformat(result["adult_verified_at"]),
                expires_at=_isoformat(result["expires_at"]),
            )
        )


@extend_schema(
    summary="Adult Verification Status",
    request=None,
    responses={
        200: AdultVerificationStatusResponseSerializer,
        401: ErrorResponseSerializer,
    },
    tags=["users"],
)
class AdultVerificationStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        result = get_adult_verification_status(user=cast(User, request.user))
        return Response(
            AdultVerificationStatusResponseSerializer(result).data,
        )
