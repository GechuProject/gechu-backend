"""
관리자 전용 RAWG Sync API

엔드포인트:
    룩업 테이블 동기화 POST /admin/sync/rawg/lookup/
    게임 전체 동기화 POST /admin/sync/rawg/games/
    단일 게임 강제 동기화 POST /admin/sync/rawg/games/{rawg_id}/
    태스크 상태 조회 GET  /admin/sync/rawg/status/{task_id}/

비고: 모든 sync 엔드포인트는 비동기 작업 시작이므로 202 Accepted 반환
"""

# from celery.result import AsyncResult
# from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
# from rest_framework import status
# from rest_framework.permissions import IsAdminUser
# from rest_framework.request import Request
# from rest_framework.response import Response
# from rest_framework.views import APIView
#
# from apps.games.serializers.rawg_sync import (
#     SyncGamesQuerySerializer,
#     TaskEnqueuedSerializer,
#     TaskStatusSerializer,
# )
# from apps.games.tasks import sync_all_games, sync_lookup_tables, sync_single_game


# TODO: RawgLookupSyncView   - POST, extend_schema, 202 반환
# TODO: RawgGamesSyncView    - POST, extend_schema, query param 검증, 202 반환
# TODO: RawgSingleGameSyncView - POST, extend_schema, path param rawg_id, 202 반환
# TODO: RawgSyncStatusView   - GET, extend_schema, AsyncResult 조회, state별 result 처리
