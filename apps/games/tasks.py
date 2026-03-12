"""
Celery Tasks - RAWG 동기화
"""

# from __future__ import annotations
#
# import logging
#
# from celery import shared_task
#
# from apps.games.rawg.exceptions import RawgRateLimitError, RawgServerError
# from apps.games.services.rawg_sync import RawgSyncService
#
# logger = logging.getLogger(__name__)

# TODO: sync_lookup_tables  - RawgServerError 자동 재시도, RawgRateLimitError 5분 수동 retry
# TODO: sync_all_games      - ordering/max_pages/fetch_detail 인자, PROGRESS 상태 업데이트, soft/hard time limit
# TODO: sync_single_game    - rawg_id 인자, RawgRateLimitError 2분 수동 retry
# TODO: incremental_sync    - 룩업 → 게임 증분(ordering="-updated", max_pages=50) 직렬 실행
