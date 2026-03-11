from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.games.serializers import PlatformListResponseSerializer
from apps.games.services.platform_list import PlatformService


@extend_schema(
    tags=["games"],
    summary="전체 플랫폼 목록 조회",
    description="전체 플랫폼 목록을 조회합니다.",
    responses={200: PlatformListResponseSerializer},
)
class PlatformListAPIView(APIView):
    def get(self, request: Request) -> Response:
        # service 호출
        platforms_data = PlatformService.get_all_platforms()

        return Response({"results": platforms_data})
