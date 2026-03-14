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
from apps.recommendations.models import UserRecommendation
from apps.recommendations.serializers import (
    RecommendationItemSerializer,
    RecommendationListResponseSerializer,
    RecommendationQuerySerializer,
)
from apps.recommendations.services import RecommendationService
from apps.users.models import User


@extend_schema(
    tags=["recommendations"],
    summary="개인화 게임 추천 목록 조회",
    description=(
        "개인화 추천 목록을 조회합니다. 추천 데이터가 준비되지 않은 경우 `202`를 반환합니다.\n"
        "준비되지 않은 상태에서는 `user_refresh` 작업이 자동으로 큐잉됩니다."
    ),
    parameters=[
        OpenApiParameter(
            "type", type=str, required=False, description="추천 유형", enum=["similarity", "preference", "hybrid"]
        ),
        OpenApiParameter("genre", type=str, required=False, description="장르 ID(복수는 콤마 구분)"),
        OpenApiParameter("tag", type=str, required=False, description="태그 ID(복수는 콤마 구분)"),
        OpenApiParameter("is_free", type=bool, required=False, description="무료 게임 필터"),
        OpenApiParameter("is_adult", type=bool, required=False, description="성인 게임 필터"),
        *PAGINATION_PARAMS,
    ],
    responses={
        200: RecommendationListResponseSerializer,
        202: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Accepted",
            examples=[
                OpenApiExample(
                    "추천 데이터 준비 중",
                    value={
                        "status_code": 202,
                        "code": "RECOMMENDATION_NOT_READY",
                        "message": "추천 데이터를 준비중입니다 잠시 후 다시 요청해주세요.",
                    },
                )
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
            value={"type": "similarity", "genre": "1", "tag": "3", "is_free": False, "is_adult": False, "page": 1},
            request_only=True,
        ),
        OpenApiExample(
            "성공 응답 예시",
            value={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "game_id": 652,
                        "name": "Cyberpunk 2077",
                        "reason": "hybrid",
                        "generated_at": "2025-06-17T00:00:00Z",
                        "rank": 1,
                        "score": "0.8612",
                        "tags": ["RPG", "Open World"],
                        "thumbnail_img_url": "https://media.example.com/cp2077.jpg",
                        "rawg_rating": "4.70",
                        "genres": [{"id": 1, "name": "Action"}],
                    }
                ],
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class RecommendationListView(ListAPIView):  # type: ignore[type-arg]
    permission_classes = [IsAuthenticated]
    serializer_class = RecommendationItemSerializer
    pagination_class = Pagination

    def get_queryset(self) -> QuerySet[UserRecommendation]:
        query_serializer = RecommendationQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)
        data = query_serializer.validated_data

        user = cast(User, self.request.user)
        if not RecommendationService.is_recommendation_ready(user=user):
            RecommendationService.enqueue_user_refresh_job_if_needed(user=user)
            raise CustomAPIException(ErrorMessages.RECOMMENDATION_NOT_READY)

        return RecommendationService.list_recommendations(
            user=user,
            rec_type=cast(str | None, data.get("type")),
            genre_ids=cast(list[int] | None, data.get("genre")),
            tag_ids=cast(list[int] | None, data.get("tag")),
            is_adult=cast(bool | None, data.get("is_adult")),
            is_free=cast(bool | None, data.get("is_free")),
        )
