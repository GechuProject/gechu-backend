from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.core.utils.pagination import PAGINATION_PARAMS, Pagination
from apps.recommendations.models import RecommendationJob
from apps.recommendations.serializers import (
    RecommendationJobItemSerializer,
    RecommendationJobListQuerySerializer,
    RecommendationJobListResponseSerializer,
)
from apps.recommendations.services import RecommendationAdminService
from apps.users.models import User


@extend_schema(
    tags=["admin"],
    summary="추천 작업 목록 조회",
    description="관리자 권한으로 추천 작업 목록을 조회합니다.",
    parameters=[
        OpenApiParameter(
            "status",
            type=str,
            required=False,
            description="작업 상태 필터",
            enum=["pending", "running", "success", "failed"],
        ),
        OpenApiParameter(
            "type",
            type=str,
            required=False,
            description="작업 유형 필터",
            enum=["user_refresh", "similarity_rebuild"],
        ),
        *PAGINATION_PARAMS,
    ],
    responses={
        200: RecommendationJobListResponseSerializer,
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
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Bad Request",
            examples=[
                OpenApiExample(
                    "잘못된 쿼리 파라미터",
                    value={
                        "status_code": ErrorMessages.INVALID_QUERY_PARAM.status_code,
                        "code": ErrorMessages.INVALID_QUERY_PARAM.name,
                        "message": ErrorMessages.INVALID_QUERY_PARAM.message,
                    },
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "요청 예시",
            value={"status": "failed", "type": "user_refresh", "page": 1, "page_size": 20},
            request_only=True,
        ),
        OpenApiExample(
            "응답 예시",
            value={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": 15,
                        "type": "user_refresh",
                        "status": "success",
                        "target_user": 1,
                        "started_at": "2025-06-10T01:00:00Z",
                        "created_at": "2025-06-10T00:59:00Z",
                    }
                ],
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class AdminRecommendationJobListView(ListAPIView):  # type: ignore[type-arg]
    permission_classes = [IsAuthenticated]
    serializer_class = RecommendationJobItemSerializer
    pagination_class = Pagination

    def get_queryset(self) -> QuerySet[RecommendationJob]:
        user = cast(User, self.request.user)
        if not user.is_staff:
            raise CustomAPIException(ErrorMessages.FORBIDDEN)

        query_serializer = RecommendationJobListQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)
        data = query_serializer.validated_data

        return RecommendationAdminService.list_recommendation_jobs(
            job_status=cast(str | None, data.get("status")),
            job_type=cast(str | None, data.get("type")),
        )
