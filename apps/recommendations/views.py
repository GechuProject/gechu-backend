from __future__ import annotations

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
from apps.core.utils.pagination import PAGINATION_PARAMS, Pagination
from apps.games.igdb import cache as igdb_cache
from apps.recommendations.serializers import (
    RecommendationListResponseSerializer,
    RecommendationQuerySerializer,
    RecommendationStatusResponseSerializer,
)
from apps.recommendations.services import RecommendationService, RecommendationStatusService
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
        *PAGINATION_PARAMS,
    ],
    responses={
        200: RecommendationListResponseSerializer,
        202: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="추천 데이터 준비 중입니다.",
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
            description="HttpOnly access_token 쿠키 인증이 필요합니다.",
        ),
    },
)
class RecommendationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        query_serializer = RecommendationQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        data = query_serializer.validated_data

        user = cast(User, request.user)
        if not RecommendationService.is_recommendation_ready(user=user):
            RecommendationService.enqueue_user_refresh_job_if_needed(user=user)
            raise CustomAPIException(ErrorMessages.RECOMMENDATION_NOT_READY)

        qs = RecommendationService.list_recommendations(
            user=user,
            rec_type=cast(str | None, data.get("type")),
        )

        # 페이지네이션
        paginator = Pagination()
        page = paginator.paginate_queryset(qs, request)
        recommendations = page if page is not None else list(qs)

        # IGDB에서 게임 정보 hydrate
        igdb_ids = [r.igdb_game_id for r in recommendations]
        games_by_id = {g["id"]: g for g in igdb_cache.get_games_by_ids(igdb_ids)}

        # 메타 정보 (generation_version, generated_at, expires_at)
        first_rec = recommendations[0] if recommendations else None

        results = []
        for r in recommendations:
            game = games_by_id.get(r.igdb_game_id, {})
            results.append(
                {
                    "rank": r.rank,
                    "score": r.score,
                    "reason": r.reason or "",
                    "game": {
                        "id": r.igdb_game_id,
                        "name": game.get("name", ""),
                        "slug": game.get("slug", ""),
                        "thumbnail_img_url": game.get("thumbnail_img_url", ""),
                        "rawg_rating": game.get("rawg_rating", 0),
                        "genres": game.get("genres", []),
                    },
                }
            )

        response_data = {
            "generation_version": first_rec.generation_version if first_rec else None,
            "generated_at": first_rec.generated_at if first_rec else None,
            "expires_at": first_rec.expires_at if first_rec else None,
            "results": results,
        }

        if page is not None:
            return paginator.get_paginated_response(results)
        return Response(response_data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["recommendations"],
    summary="추천 생성 상태 조회",
    description="추천 생성 상태를 조회합니다.",
    responses={
        200: RecommendationStatusResponseSerializer,
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="HttpOnly access_token 쿠키 인증이 필요합니다.",
        ),
    },
)
class RecommendationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        result = RecommendationStatusService.get_status(user=user)
        return Response(result, status=status.HTTP_200_OK)
