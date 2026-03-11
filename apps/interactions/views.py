from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import cast

from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.games.models import Game
from apps.interactions.models import InteractionContextRule, InteractionLog, InteractionWeightRule
from apps.interactions.serializers import (
    InteractionViewLogRequestSerializer,
    InteractionViewLogResponseSerializer,
)
from apps.users.models import User


@extend_schema(
    tags=["Interactions"],
    summary="게임 조회 행동 기록",
    description=(
        "게임 조회(view) 행동을 기록합니다.\n\n"
        "- 최초 기록 시: `201` + `logged=true`\n"
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
        payload = request.data
        if "game_id" not in payload or "source" not in payload:
            raise CustomAPIException(ErrorMessages.GAME_ID_OR_SOURCE_MISSING)

        serializer = InteractionViewLogRequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        game = Game.objects.filter(id=data["game_id"], is_visible=True).first()
        if game is None:
            raise CustomAPIException(ErrorMessages.GAME_NOT_FOUND)

        weight_rule = InteractionWeightRule.objects.filter(
            interaction_type=InteractionLog.ActionType.VIEW,
            is_active=True,
        ).first()
        if weight_rule is None:
            raise CustomAPIException(ErrorMessages.INTERACTION_TYPE_NOT_FOUND)

        context_rule = InteractionContextRule.objects.filter(
            interaction_source=data["source"],
        ).first()
        if context_rule is None:
            raise CustomAPIException(ErrorMessages.SOURCE_NOT_FOUND)

        user = cast(User, request.user)
        latest_reusable_log = (
            InteractionLog.objects.filter(
                user=user,
                game=game,
                type=InteractionLog.ActionType.VIEW,
                weight__isnull=False,
            )
            .order_by("-created_at")
            .first()
        )
        if (
            latest_reusable_log is not None
            and weight_rule.cooldown_seconds > 0
            and latest_reusable_log.created_at >= timezone.now() - timedelta(seconds=weight_rule.cooldown_seconds)
        ):
            return Response(
                {
                    "id": latest_reusable_log.id,
                    "type": latest_reusable_log.type,
                    "logged_at": latest_reusable_log.created_at,
                },
                status=200,
            )

        repeat_count = InteractionLog.objects.filter(
            user=user,
            game=game,
            type=InteractionLog.ActionType.VIEW,
        ).count()
        weight: Decimal = (
            weight_rule.base_weight * context_rule.multiplier * (weight_rule.repeat_decay**repeat_count)
        ).quantize(Decimal("0.0001"))

        log = InteractionLog.objects.create(
            user=user,
            game=game,
            type=InteractionLog.ActionType.VIEW,
            source=data["source"],
            weight=weight,
            metadata=data.get("metadata"),
        )

        return Response(
            {
                "id": log.id,
                "type": log.type,
                "logged_at": log.created_at,
            },
            status=201,
        )
