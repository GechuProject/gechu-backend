from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.games.serializers.game_list import (
    GameListQuerySerializer,
    GameListResponseSerializer,
)
from apps.games.services.game_list import GameService
from apps.users.services.search_recent_service import save_recent_search_keyword


@extend_schema(
    tags=["games"],
    summary="게임 목록 조회",
    description="게임 목록 조회 (검색/필터/정렬) - IGDB API 기반",
    parameters=[
        OpenApiParameter("search", type=str, required=False, description="게임 이름 검색"),
        OpenApiParameter("genre_ids", type=str, required=False, description="장르 ID 리스트(콤마 구분)"),
        OpenApiParameter("genre_name", type=str, required=False, description="장르 NAME"),
        OpenApiParameter("platform_ids", type=str, required=False, description="플랫폼 ID 리스트(콤마 구분)"),
        OpenApiParameter("tag_ids", type=str, required=False, description="태그 ID 리스트(콤마 구분)"),
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
class GameListView(APIView):
    def get(self, request: Request) -> Response:
        query_serializer = GameListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        data = query_serializer.validated_data
        if self.request.user.is_authenticated and data.get("search"):
            save_recent_search_keyword(user=self.request.user, keyword=data["search"])

        page = data.get("page", 1)
        page_size = data.get("page_size", 20)

        genre_name = data.get("genre_name")

        if genre_name:
            items = GameService.top_n_by_genre(genre_name)
            next_url = None
            previous_url = None
        else:
            results = GameService.list_games(
                search=data.get("search"),
                genre_ids=data.get("genre_ids"),
                platform_ids=data.get("platform_ids"),
                tag_ids=data.get("tag_ids"),
                ordering=data.get("ordering"),
                page=page,
                page_size=page_size,
            )

            # has_next 판단: page_size+1 개를 요청해서
            has_next = len(results) > page_size
            items = results[:page_size]

            # next/previous URL 생성
            path = request.build_absolute_uri(request.path)
            next_url = f"{path}?page={page + 1}&page_size={page_size}" if has_next else None
            previous_url = f"{path}?page={page - 1}&page_size={page_size}" if page > 1 else None

        response_data = {
            "next": next_url,
            "previous": previous_url,
            "results": items,
        }

        serializer = GameListResponseSerializer(response_data)

        return Response(serializer.data, status=status.HTTP_200_OK)
