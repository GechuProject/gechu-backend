from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.preferences.serializers import PreferenceMeResponseSerializer


class PreferenceMeRetrieveView(APIView):
    """GET /api/v1/preferences/me - 내 선호 설정 전체 조회"""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        serializer = PreferenceMeResponseSerializer(request.user)
        return Response(serializer.data)
