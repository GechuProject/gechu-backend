from __future__ import annotations

from typing import cast

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.interactions.serializers import (
    InteractionWeightRuleItemSerializer,
    InteractionWeightRuleListResponseSerializer,
)
from apps.interactions.services import InteractionAdminRuleService
from apps.users.models import User


@extend_schema(
    tags=["admin"],
    summary="행동 가중치 목록 조회",
    description="관리자 권한으로 행동 가중치 규칙 목록을 조회합니다.",
    responses={
        200: InteractionWeightRuleListResponseSerializer,
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Unauthorized",
            examples=[
                OpenApiExample(
                    "인증 필요",
                    value={
                        "status_code": ErrorMessages.UNAUTHORIZED.status_code,
                        "code": ErrorMessages.UNAUTHORIZED.name,
                        "message": ErrorMessages.UNAUTHORIZED.message,
                    },
                )
            ],
        ),
        403: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Forbidden",
            examples=[
                OpenApiExample(
                    "관리자 권한 필요",
                    value={
                        "status_code": ErrorMessages.FORBIDDEN.status_code,
                        "code": ErrorMessages.FORBIDDEN.name,
                        "message": ErrorMessages.FORBIDDEN.message,
                    },
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "응답 예시",
            value={
                "results": [
                    {
                        "interaction_type": "view",
                        "base_weight": "1.00",
                        "cooldown_seconds": 60,
                        "repeat_decay": "0.800",
                        "updated_at": "2025-01-01T00:00:00Z",
                    }
                ]
            },
            response_only=True,
            status_codes=["200"],
        )
    ],
)
class AdminInteractionWeightRuleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        if not user.is_staff:
            raise CustomAPIException(ErrorMessages.FORBIDDEN)

        rules = InteractionAdminRuleService.list_weight_rules()
        serializer = InteractionWeightRuleItemSerializer(rules, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)
