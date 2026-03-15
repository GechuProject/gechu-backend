from __future__ import annotations

from django.core.cache import cache
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import IgdbSyncRequestSerializer, TaskEnqueuedSerializer
from .tasks import incremental_sync, sync_all_games

_LOCK_KEY = "igdb_sync_running"


class IgdbSyncView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Admin"],
        summary="IGDB 게임 데이터 동기화 실행",
        description=(
            "IGDB API 데이터를 DB에 동기화합니다.\n\n"
            "- `full_sync=false`(기본): 최근 50페이지만 동기화\n"
            "- `full_sync=true`: 전체 재동기화\n\n"
            "비동기(Celery) 태스크로 실행되며, 202 Accepted 즉시 반환합니다.\n"
            "이미 동기화가 진행 중인 경우 409를 반환합니다."
        ),
        request=IgdbSyncRequestSerializer,
        responses={
            202: OpenApiResponse(
                response=TaskEnqueuedSerializer,
                examples=[
                    OpenApiExample(
                        "성공 예시",
                        value={
                            "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            "status": "pending",
                            "message": "IGDB 동기화 작업이 시작되었습니다.",
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description="인증이 필요합니다."),
            403: OpenApiResponse(description="관리자 권한이 필요합니다."),
            409: OpenApiResponse(description="이미 동기화 작업이 진행 중입니다."),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = IgdbSyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        full_sync = serializer.validated_data["full_sync"]

        if cache.get(_LOCK_KEY):
            return Response(
                {
                    "status_code": 409,
                    "code": "SYNC_ALREADY_RUNNING",
                    "message": "이미 동기화 작업이 진행 중입니다.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        if full_sync:
            task = sync_all_games.delay(max_pages=None)
        else:
            task = incremental_sync.delay()

        response_serializer = TaskEnqueuedSerializer(
            data={
                "job_id": task.id,
                "status": "pending",
                "message": "IGDB 동기화 작업이 시작되었습니다.",
            }
        )
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.validated_data, status=status.HTTP_202_ACCEPTED)
