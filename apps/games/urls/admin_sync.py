# from django.urls import path
#
# from apps.games.views.rawg_sync import (
#     RawgGamesSyncView,
#     RawgLookupSyncView,
#     RawgSingleGameSyncView,
#     RawgSyncStatusView,
# )
#
from django.urls import URLPattern, URLResolver

urlpatterns: list[URLPattern | URLResolver] = [
    #     # 룩업 테이블 동기화
    #     path("lookup/", RawgLookupSyncView.as_view(), name="admin-rawg-sync-lookup"),
    #     # 게임 전체 동기화
    #     path("games/", RawgGamesSyncView.as_view(), name="admin-rawg-sync-games"),
    #     # 단일 게임 강제 동기화
    #     path("games/<int:rawg_id>/", RawgSingleGameSyncView.as_view(), name="admin-rawg-sync-single-game"),
    #     # Task 상태 조회
    #     path("status/<str:task_id>/", RawgSyncStatusView.as_view(), name="admin-rawg-sync-status"),
]
