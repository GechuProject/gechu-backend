from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.generics import ListAPIView

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.core.utils.pagination import Pagination
from apps.games.models.catalog import Game
from apps.games.serializers.game_list import (
    GameListQuerySerializer,
    GameListResponseSerializer,
)
from apps.games.services.game_list import GameService


@extend_schema(
    tags=["games"],
    summary="게임 목록 조회",
    description="게임 목록 조회 (검색/필터/정렬)",
    parameters=[
        OpenApiParameter("search", type=str, required=False, description="게임 이름 검색"),
        OpenApiParameter("genre_ids", type=str, required=False, description="장르 ID 리스트(콤마 구분)"),
        OpenApiParameter("platform_ids", type=str, required=False, description="플랫폼 ID 리스트(콤마 구분)"),
        OpenApiParameter("tag_ids", type=str, required=False, description="태그 ID 리스트(콤마 구분)"),
        OpenApiParameter(
            "esrb_rating",
            type=str,
            required=False,
            description="ESRB 등급 필터링",
            enum=["everyone", "everyone_10_plus", "teen", "mature", "adults_only", "rating_pending", "unknown"],
        ),
        OpenApiParameter(
            "ordering",
            type=str,
            required=False,
            description="정렬",
            enum=["rawg_rating", "-rawg_rating", "released", "-released", "rawg_added", "-rawg_added"],
        ),
        OpenApiParameter("page", type=int, required=False, description="조회할 페이지 번호"),
        OpenApiParameter("page_size", type=int, required=False, description="페이지당 결과 수(최대: 100)"),
    ],
    responses={
        200: GameListResponseSerializer,
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
                ),
                OpenApiExample(
                    "지원하지 않는 정렬 기준",
                    value={
                        "status_code": ErrorMessages.INVALID_ORDERING.status_code,
                        "code": ErrorMessages.INVALID_ORDERING.name,
                        "message": ErrorMessages.INVALID_ORDERING.message,
                    },
                ),
            ],
        ),
    },
)
class GameListView(ListAPIView):  # type: ignore[type-arg]
    serializer_class = GameListResponseSerializer
    pagination_class = Pagination

    def get_queryset(self) -> QuerySet[Game]:
        # 쿼리 파라미터 검증
        query_serializer = GameListQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)

        data = query_serializer.validated_data

        # 서비스 호출
        return GameService.list_games(
            user=self.request.user,
            search=data.get("search"),
            genre_ids=data.get("genre_ids"),
            platform_ids=data.get("platform_ids"),
            tag_ids=data.get("tag_ids"),
            esrb_rating=data.get("esrb_rating"),
            ordering=data.get("ordering"),
        )