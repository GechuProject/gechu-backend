from __future__ import annotations

from decimal import Decimal
from typing import cast

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.interactions.serializers import (
    InteractionContextRuleItemSerializer,
    InteractionContextRuleListResponseSerializer,
    InteractionWeightRuleItemSerializer,
    InteractionWeightRuleListResponseSerializer,
    InteractionWeightRuleUpdateRequestSerializer,
)
from apps.interactions.services import InteractionAdminContextRuleService, InteractionAdminRuleService
from apps.users.models import User


@extend_schema(
    tags=["admin"],
    summary="맥락 가중치 목록 조회",
    description=(
        "관리자 권한으로 맥락(발생 위치)별 가중치 규칙 목록을 조회합니다. "
        "list_page, detail_page, search_result, recommendation, saved_page, onboarding 등 "
        "interaction_source별 multiplier와 updated_at이 반환됩니다. "
        "쿼리 파라미터 없이 GET 요청만 보내면 됩니다."
    ),
    responses={
        200: InteractionContextRuleListResponseSerializer,
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="인증되지 않음. Authorization 헤더에 유효한 Bearer 토큰이 필요합니다.",
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
            description="권한 없음. is_staff=True인 관리자 계정만 호출할 수 있습니다.",
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
            "성공 시 응답 예시",
            value={
                "results": [
                    {
                        "interaction_source": "list_page",
                        "multiplier": "0.90",
                        "updated_at": "2025-05-01T00:00:00Z",
                    },
                    {
                        "interaction_source": "recommendation",
                        "multiplier": "1.40",
                        "updated_at": "2025-05-01T00:00:00Z",
                    },
                ]
            },
            response_only=True,
            status_codes=["200"],
        )
    ],
)
class AdminInteractionContextRuleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        if not user.is_staff:
            raise CustomAPIException(ErrorMessages.FORBIDDEN)

        rules = InteractionAdminContextRuleService.list_context_rules()
        serializer = InteractionContextRuleItemSerializer(rules, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)


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


@extend_schema(
    tags=["admin"],
    summary="행동 가중치 수정",
    description="관리자 권한으로 특정 행동 타입의 가중치 규칙을 수정합니다.",
    parameters=[
        OpenApiParameter(
            name="interaction_type",
            type=str,
            location=OpenApiParameter.PATH,
            required=True,
            description="행동 타입",
            enum=["view", "search", "saved_add", "saved_remove", "like", "dislike", "preference_set", "store_click"],
        )
    ],
    request=InteractionWeightRuleUpdateRequestSerializer,
    responses={
        200: InteractionWeightRuleItemSerializer,
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Bad Request",
            examples=[
                OpenApiExample(
                    "base_weight 범위 오류",
                    value={
                        "status_code": ErrorMessages.BASE_WEIGHT_INVALID.status_code,
                        "code": ErrorMessages.BASE_WEIGHT_INVALID.name,
                        "message": ErrorMessages.BASE_WEIGHT_INVALID.message,
                    },
                ),
                OpenApiExample(
                    "입력값 오류",
                    value={
                        "status_code": ErrorMessages.VALIDATION_ERROR.status_code,
                        "code": ErrorMessages.VALIDATION_ERROR.name,
                        "message": ErrorMessages.VALIDATION_ERROR.message,
                    },
                ),
            ],
        ),
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
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Not Found",
            examples=[
                OpenApiExample(
                    "행동 타입 없음",
                    value={
                        "status_code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.status_code,
                        "code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.name,
                        "message": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.message,
                    },
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "요청 예시",
            value={
                "base_weight": 1.50,
                "cooldown_seconds": 120,
            },
            request_only=True,
        ),
        OpenApiExample(
            "응답 예시",
            value={
                "interaction_type": "view",
                "base_weight": "1.50",
                "cooldown_seconds": 120,
                "repeat_decay": "0.800",
                "updated_at": "2025-06-01T15:00:00Z",
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class AdminInteractionWeightRuleUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, interaction_type: str) -> Response:
        user = cast(User, request.user)
        if not user.is_staff:
            raise CustomAPIException(ErrorMessages.FORBIDDEN)

        req_serializer = InteractionWeightRuleUpdateRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        data = req_serializer.validated_data

        rule = InteractionAdminRuleService.update_weight_rule(
            interaction_type=interaction_type,
            base_weight=cast(Decimal | None, data.get("base_weight")),
            cooldown_seconds=cast(int | None, data.get("cooldown_seconds")),
            repeat_decay=cast(Decimal | None, data.get("repeat_decay")),
        )
        if rule is None:
            raise CustomAPIException(ErrorMessages.INTERACTION_TYPE_NOT_FOUND)

        serializer = InteractionWeightRuleItemSerializer(rule)
        return Response(serializer.data, status=status.HTTP_200_OK)
