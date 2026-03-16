from typing import cast

from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.users.models.user import User
from apps.users.serializers.adult_verification import (
    AdultVerificationCallbackRequestSerializer,
    AdultVerificationCallbackResponseSerializer,
    AdultVerificationStatusResponseSerializer,
)
from apps.users.services.adult_verification_service import (
    complete_adult_verification,
    get_adult_verification_status,
    initiate_adult_verification,
)


@extend_schema(
    summary="비바톤 성인인증 리다이렉트",
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
    summary="성인 인증 비바톤 콜백",
    request=None,
    parameters=[
        OpenApiParameter(
            name="code",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="비바톤 OAuth 인증 코드",
        ),
        OpenApiParameter(
            name="state",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="비바톤 OAuth state 값",
        ),
    ],
    responses={
        200: AdultVerificationCallbackResponseSerializer,
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="INVALID_STATE, OAUTH_CALLBACK_ERROR, UNDERAGE, ALREADY_VERIFIED",
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

    def get(self, request: Request) -> Response:
        serializer = AdultVerificationCallbackRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        result = complete_adult_verification(**serializer.validated_data)
        return Response(
            AdultVerificationCallbackResponseSerializer(result).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="성인 인증 상태 조회",
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
            status=status.HTTP_200_OK,
        )
