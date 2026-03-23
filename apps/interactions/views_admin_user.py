from __future__ import annotations

from typing import cast

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.permissions import IsStaffAdmin
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.core.utils.pagination import PAGINATION_PARAMS, Pagination
from apps.interactions.serializers import (
    AdminUserInteractionItemSerializer,
    AdminUserInteractionListResponseSerializer,
    AdminUserInteractionQuerySerializer,
)
from apps.interactions.services import InteractionAdminUserInteractionService
from apps.users.models import User


@extend_schema(
    tags=["admin"],
    summary="어드민 - 유저 활동 로그 조회",
    description=(
        "관리자(staff) 전용입니다. 지정한 유저의 InteractionLog를 최신순으로 페이지네이션 조회합니다. "
        "query `type`으로 행동 유형(view, like, dislike, search, saved_add, saved_remove)을 필터할 수 있습니다. "
        "게임과 무관한 로그는 `game_id`가 null일 수 있습니다."
    ),
    parameters=[
        OpenApiParameter(
            name="user_id",
            type=int,
            location=OpenApiParameter.PATH,
            required=True,
            description="활동 로그를 조회할 유저 ID (pk)",
        ),
        OpenApiParameter(
            name="type",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="행동 유형 필터",
            enum=["view", "like", "dislike", "search", "saved_add", "saved_remove"],
        ),
        *PAGINATION_PARAMS,
    ],
    responses={
        200: AdminUserInteractionListResponseSerializer,
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="인증되지 않음.",
            examples=[
                OpenApiExample(
                    "UNAUTHORIZED",
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
            description="staff가 아닌 경우",
            examples=[
                OpenApiExample(
                    "FORBIDDEN",
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
            description="유저가 없을 때",
            examples=[
                OpenApiExample(
                    "USER_NOT_FOUND",
                    value={
                        "status_code": ErrorMessages.USER_NOT_FOUND.status_code,
                        "code": ErrorMessages.USER_NOT_FOUND.name,
                        "message": ErrorMessages.USER_NOT_FOUND.message,
                    },
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "성공 시 응답 예시",
            value={
                "count": 20,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "type": "like",
                        "game_id": 15,
                        "created_at": "2025-02-01T10:00:00Z",
                    }
                ],
            },
            response_only=True,
            status_codes=["200"],
        )
    ],
)
class AdminUserInteractionListView(APIView):
    permission_classes = [IsStaffAdmin]

    def get(self, request: Request, user_id: int) -> Response:
        if not User.objects.filter(pk=user_id).exists():
            raise CustomAPIException(ErrorMessages.USER_NOT_FOUND)

        query_serializer = AdminUserInteractionQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        q = query_serializer.validated_data

        qs = InteractionAdminUserInteractionService.list_interaction_logs(
            user_id=user_id,
            interaction_type=cast(str | None, q.get("type")),
        )
        paginator = Pagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminUserInteractionItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
