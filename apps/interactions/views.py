from __future__ import annotations

from typing import cast

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.interactions.serializers import (
    InteractionViewLogRequestSerializer,
    InteractionViewLogResponseSerializer,
)
from apps.interactions.services import record_view_interaction
from apps.users.models import User


@extend_schema(
    tags=["Interactions"],
    summary="게임 조회 행동 기록",
    description=(
        "게임 조회(view) 행동을 기록합니다.\n\n"
        "- 최초 기록 시: `201`\n"
        "- 쿨다운 내 중복 요청 시: 로그를 추가 생성하지 않고 `200`으로 기존 최근 로그를 반환합니다.\n"
        "- 가중치는 `interaction_weight_rules`(type=view)와 "
        "`interaction_context_rules`(source) 조합으로 계산됩니다."
    ),
    request=InteractionViewLogRequestSerializer,
    examples=[
        OpenApiExample(
            "요청 예시",
            value={
                "game_id": 1,
                "source": "recommendation",
                "metadata": {"page": 1, "section": "home_reco"},
            },
            request_only=True,
        ),
        OpenApiExample(
            "생성 응답 예시 (201)",
            value={
                "id": 101,
                "type": "view",
                "logged_at": "2026-03-11T08:30:00Z",
            },
            response_only=True,
            status_codes=["201"],
        ),
        OpenApiExample(
            "쿨다운 무시 응답 예시 (200)",
            value={
                "id": 101,
                "type": "view",
                "logged_at": "2026-03-11T08:30:00Z",
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
    responses={
        200: InteractionViewLogResponseSerializer,
        201: InteractionViewLogResponseSerializer,
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Bad Request",
            examples=[
                OpenApiExample(
                    "필수값 누락",
                    value={
                        "status_code": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.status_code,
                        "code": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.name,
                        "message": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.message,
                    },
                ),
                OpenApiExample(
                    "source 값 오류",
                    value={
                        "status_code": ErrorMessages.INVALID_SOURCE.status_code,
                        "code": ErrorMessages.INVALID_SOURCE.name,
                        "message": ErrorMessages.INVALID_SOURCE.message,
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
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Not Found",
            examples=[
                OpenApiExample(
                    "게임 없음",
                    value={
                        "status_code": ErrorMessages.GAME_NOT_FOUND.status_code,
                        "code": ErrorMessages.GAME_NOT_FOUND.name,
                        "message": ErrorMessages.GAME_NOT_FOUND.message,
                    },
                ),
                OpenApiExample(
                    "view 룰 없음",
                    value={
                        "status_code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.status_code,
                        "code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.name,
                        "message": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.message,
                    },
                ),
                OpenApiExample(
                    "source 룰 없음",
                    value={
                        "status_code": ErrorMessages.SOURCE_NOT_FOUND.status_code,
                        "code": ErrorMessages.SOURCE_NOT_FOUND.name,
                        "message": ErrorMessages.SOURCE_NOT_FOUND.message,
                    },
                ),
            ],
        ),
    },
)
class InteractionViewLogCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = InteractionViewLogRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = cast(User, request.user)
        log, created = record_view_interaction(
            user=user,
            game_id=data["game_id"],
            source=data["source"],
            metadata=data.get("metadata"),
        )

        response_serializer = InteractionViewLogResponseSerializer(log)
        return Response(response_serializer.data, status=201 if created else 200)
