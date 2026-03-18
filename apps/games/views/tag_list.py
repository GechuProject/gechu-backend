from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.games.serializers import (
    TagListQuerySerializer,
    TagListResponseSerializer,
)
from apps.games.services.tag_list import TagService


@extend_schema(
    tags=["games"],
    summary="전체 태그 목록 조회",
    description="전체 태그 목록을 조회합니다.",
    responses={
        200: TagListResponseSerializer,
    },
)
class TagListAPIView(APIView):
    def get(self, request: Request) -> Response:
        # Service 호출
        result = TagService.get_tag_list()

        # Serializer 응답 직렬화
        serializer = TagListResponseSerializer({"results": result["results"]})

        return Response(serializer.data)
