"""
RawgSyncService: RAWG 데이터 → DB upsert 서비스 레이어
"""

# from __future__ import annotations
#
# import logging
#
# from django.db import transaction
#
# from apps.games.models import (
#     ExternalStore, Game, GameGenre, GameMedia, GamePlatform, GameStore, GameTag, Genre, Platform, Tag,
# )
# from apps.games.rawg.client import RawgClient
# from apps.games.rawg.converters import (
#     convert_game, convert_genre, convert_platform, convert_screenshot,
#     convert_store, convert_tag, convert_trailer,
#     extract_genre_rawg_ids, extract_platform_entries,
#     extract_store_entries, extract_tag_rawg_ids,
# )
#
# logger = logging.getLogger(__name__)

# TODO: _GAME_UPDATE_FIELDS / _GENRE_UPDATE_FIELDS / _PLATFORM_UPDATE_FIELDS
#       _TAG_UPDATE_FIELDS / _STORE_UPDATE_FIELDS 상수 정의 (is_visible 제외)


# class RawgSyncService:
#
#     def __init__(self, client: RawgClient | None = None) -> None:
#         self._client = client or RawgClient()

# TODO: sync_genres / sync_platforms / sync_tags / sync_stores

# TODO: sync_games(ordering, max_pages, fetch_detail) → {"pages_processed", "synced", "failed"}
# TODO: sync_single_game(rawg_id) → {"rawg_id", "game_id"}

# TODO: _sync_game_page(page_results, fetch_detail) → (synced, failed)
# TODO: _upsert_game(game_dict) → Game
# TODO: _sync_game_relations(game, list_raw, detail_raw)
# TODO: _sync_game_genres / _sync_game_tags  ← through 테이블 직접 조작, set() 사용 금지
# TODO: _sync_game_platforms / _sync_game_stores
# TODO: _sync_game_media  ← 스크린샷·트레일러 각각 독립적으로 예외 처리
