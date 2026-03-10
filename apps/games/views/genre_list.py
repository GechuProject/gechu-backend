from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.games.serializers import GenreListResponseSerializer
from apps.games.services.genre_list import GenreService


@extend_schema(
    tags=["games"],
    summary="전체 장르 목록 조회",
    description="전체 장르 목록을 조회합니다.",
    responses={
        200: GenreListResponseSerializer,
    },
)
class GenreListAPIView(APIView):
    def get(self, request: Request) -> Response:
        # Service 호출
        genres_data: list[dict[str, Any]] = GenreService.get_all_genres()

        # Response Serializer 적용
        list_serializer = GenreListResponseSerializer({"results": genres_data})

        return Response(list_serializer.data)
