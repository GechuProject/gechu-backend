from typing import Any

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.games.serializers import SimilarGameResponseSerializer, SimilarGameQueryParamsSerializer
from apps.games.services.similar_game import SimilarGameService


class SimilarGamesListResponseSerializer(serializers.Serializer[dict[str, Any]]):
    results = SimilarGameResponseSerializer(many=True)


@extend_schema(
    tags=["games"],
    summary="유사 게임 목록 조회",
    description="유사 게임 목록 조회",
    parameters=[
        OpenApiParameter("limit", type=int, required=False, description="조회할 최대 유사 게임 수 (기본 10)"),
    ],
    responses={
        200: SimilarGamesListResponseSerializer,
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Not Found",
            examples=[
                OpenApiExample(
                    "게임 찾을 수 없음",
                    value={
                        "status_code": ErrorMessages.GAME_NOT_FOUND.status_code,
                        "code": ErrorMessages.GAME_NOT_FOUND.name,
                        "message": ErrorMessages.GAME_NOT_FOUND.message,
                    },
                ),
            ],
        ),
    },
)
class SimilarGameListView(APIView):
    def get(self, request: Request, game_id: int) -> Response:
        # 쿼리 파라미터 검증
        query_serializer = SimilarGameQueryParamsSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        limit = query_serializer.validated_data.get("limit", 10)

        # Service 호출
        similar_games = SimilarGameService.similar_game(game_id=game_id, limit=limit)

        return Response({"results": similar_games})
