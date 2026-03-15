"""
IgdbSyncService: IGDB 데이터 → DB upsert 서비스 레이어

설계 원칙:
- RAWG RawgSyncService와 동일한 인터페이스 유지
- rawg_id 필드에 IGDB id 저장 (기존 모델 재사용)
- bulk_create(update_conflicts=True)로 upsert 처리
- M2M은 through 테이블 직접 조작
- is_visible sync 시 덮어쓰지 않음

RAWG와 다른 점:
    - 스토어 매칭: rawg_id 대신 slug로 매칭
    - 태그: keywords → Tag 모델 재사용
    - 미디어: screenshots/videos가 게임 응답에 포함됨 (별도 API 호출 불필요)
"""

from __future__ import annotations

import logging
from typing import Any

from apps.games.models import (
    ExternalStore,
    Game,
    GameGenre,
    GameMedia,
    GamePlatform,
    GameStore,
    GameTag,
    Genre,
    Platform,
    Tag,
)

from .client import IgdbClient
from .converters import (
    convert_game,
    convert_genre,
    convert_platform,
    convert_screenshot,
    convert_tag,
    convert_trailer,
    extract_genre_igdb_ids,
    extract_keyword_igdb_ids,
    extract_platform_entries,
    extract_store_entries,
)

logger = logging.getLogger(__name__)

_GAME_UPDATE_FIELDS = [
    "slug",
    "name",
    "description",
    "released",
    "tba",
    "thumbnail_img_url",
    "website",
    "rawg_rating",
    "rawg_ratings_count",
    "metacritic",
    "rawg_added",
    "playtime",
    "esrb_rating",
    "age_rating_min",
    "rawg_updated",
    "synced_at",
]

_GENRE_UPDATE_FIELDS = ["name", "slug"]
_PLATFORM_UPDATE_FIELDS = ["name", "slug"]
_TAG_UPDATE_FIELDS = ["name", "slug"]


class IgdbSyncService:
    """
    IGDB API → DB 동기화 서비스

    사용 예:
        service = IgdbSyncService()
        service.sync_genres()
        service.sync_games(max_pages=10)
    """

    def __init__(self, client: IgdbClient | None = None) -> None:
        self._client = client or IgdbClient()

    # 룩업 테이블 ------------------------------------------

    def sync_genres(self) -> dict[str, int]:
        """IGDB /genres → DB upsert"""
        total = 0
        for page in self._client.iter_genres():
            objs = [Genre(**convert_genre(raw)) for raw in page]
            Genre.objects.bulk_create(
                objs,
                update_conflicts=True,
                unique_fields=["rawg_id"],
                update_fields=_GENRE_UPDATE_FIELDS,
            )
            total += len(objs)
        logger.info("Genre sync 완료: %d건", total)
        return {"synced": total}

    def sync_platforms(self) -> dict[str, int]:
        """IGDB /platforms → DB upsert"""
        total = 0
        for page in self._client.iter_platforms():
            objs = [Platform(**convert_platform(raw)) for raw in page]
            Platform.objects.bulk_create(
                objs,
                update_conflicts=True,
                unique_fields=["rawg_id"],
                update_fields=_PLATFORM_UPDATE_FIELDS,
            )
            total += len(objs)
        logger.info("Platform sync 완료: %d건", total)
        return {"synced": total}

    def sync_tags(self) -> dict[str, int]:
        """IGDB /keywords → Tag DB upsert"""
        total = 0
        seen: set[int] = set()
        for page in self._client.iter_keywords():
            objs = []
            for raw in page:
                data = convert_tag(raw)
                if data["rawg_id"] in seen:
                    continue
                seen.add(data["rawg_id"])
                objs.append(Tag(**data))
            Tag.objects.bulk_create(
                objs,
                update_conflicts=True,
                unique_fields=["rawg_id"],
                update_fields=_TAG_UPDATE_FIELDS,
            )
            total += len(objs)
        logger.info("Tag(keyword) sync 완료: %d건", total)
        return {"synced": total}

    # Game sync ------------------------------------------

    def sync_games(
        self,
        max_pages: int | None = None,
        fetch_detail: bool = False,  # IGDB는 iter_games에 모든 필드 포함
    ) -> dict[str, int]:
        """IGDB /games 전체 동기화"""
        total_synced = 0
        total_failed = 0
        pages = 0

        for page in self._client.iter_games():
            if max_pages and pages >= max_pages:
                break

            synced, failed = self._sync_game_page(page)
            total_synced += synced
            total_failed += failed
            pages += 1

            logger.info(
                "게임 sync 진행 page=%s synced=%s failed=%s",
                pages,
                total_synced,
                total_failed,
            )

        return {
            "pages_processed": pages,
            "synced": total_synced,
            "failed": total_failed,
        }

    def _sync_game_page(self, page_results: list[dict[str, Any]]) -> tuple[int, int]:
        """게임 목록 한 페이지 처리"""
        games_data = []
        raw_map: dict[int, dict[str, Any]] = {}

        for raw in page_results:
            try:
                game_dict = convert_game(raw)
                games_data.append(game_dict)
                raw_map[raw["id"]] = raw
            except Exception:
                logger.exception("게임 변환 실패 igdb_id=%s", raw.get("id"))

        if not games_data:
            return 0, len(page_results)

        Game.objects.bulk_create(
            [Game(**g) for g in games_data],
            update_conflicts=True,
            unique_fields=["rawg_id"],
            update_fields=_GAME_UPDATE_FIELDS,
        )

        igdb_ids = [g["rawg_id"] for g in games_data]
        games = Game.objects.in_bulk(igdb_ids, field_name="rawg_id")

        synced = 0
        for igdb_id, game in games.items():
            try:
                raw = raw_map[igdb_id]
                self._sync_game_relations(game, raw)
                self._sync_game_media(game, raw)
                synced += 1
            except Exception:
                logger.exception("relation sync 실패 igdb_id=%s", igdb_id)

        failed = len(page_results) - synced
        return synced, failed

    # Relations ------------------------------------------

    def _sync_game_relations(self, game: Game, raw: dict[str, Any]) -> None:
        self._sync_game_genres(game, raw)
        self._sync_game_tags(game, raw)
        self._sync_game_platforms(game, raw)
        self._sync_game_stores(game, raw)

    def _sync_game_genres(self, game: Game, raw: dict[str, Any]) -> None:
        igdb_ids = extract_genre_igdb_ids(raw)
        if not igdb_ids:
            return
        genre_map = {g.rawg_id: g.id for g in Genre.objects.filter(rawg_id__in=igdb_ids)}
        objs = [GameGenre(game_id=game.id, genre_id=genre_map[i]) for i in igdb_ids if i in genre_map]
        GameGenre.objects.bulk_create(objs, ignore_conflicts=True)

    def _sync_game_tags(self, game: Game, raw: dict[str, Any]) -> None:
        igdb_ids = extract_keyword_igdb_ids(raw)
        if not igdb_ids:
            return
        tag_map = {t.rawg_id: t.id for t in Tag.objects.filter(rawg_id__in=igdb_ids)}
        objs = [GameTag(game_id=game.id, tag_id=tag_map[i]) for i in igdb_ids if i in tag_map]
        GameTag.objects.bulk_create(objs, ignore_conflicts=True)

    def _sync_game_platforms(self, game: Game, raw: dict[str, Any]) -> None:
        entries = extract_platform_entries(raw)
        if not entries:
            return
        raw_ids = [e["platform_rawg_id"] for e in entries]
        platform_map = {p.rawg_id: p.id for p in Platform.objects.filter(rawg_id__in=raw_ids)}
        objs = [
            GamePlatform(
                game_id=game.id,
                platform_id=platform_map[e["platform_rawg_id"]],
                requirements_minimum=e["requirements_minimum"],
                requirements_recommended=e["requirements_recommended"],
            )
            for e in entries
            if e["platform_rawg_id"] in platform_map
        ]
        GamePlatform.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["game", "platform"],
            update_fields=["requirements_minimum", "requirements_recommended"],
        )

    def _sync_game_stores(self, game: Game, raw: dict[str, Any]) -> None:
        entries = extract_store_entries(raw)
        if not entries:
            return

        slugs = [e["store_slug"] for e in entries]
        store_map = {s.slug: s.id for s in ExternalStore.objects.filter(slug__in=slugs)}

        seen: set[int] = set()
        objs = []
        for e in entries:
            if e["store_slug"] not in store_map:
                continue
            store_id = store_map[e["store_slug"]]
            if store_id in seen:
                continue
            seen.add(store_id)
            objs.append(
                GameStore(
                    game_id=game.id,
                    store_id=store_id,
                    url=e["url"],
                )
            )

        GameStore.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["game", "store"],
            update_fields=["url"],
        )

    # Media ------------------------------------------

    def _sync_game_media(self, game: Game, raw: dict[str, Any]) -> None:
        """
        IGDB 응답에 포함된 screenshots/videos → GameMedia upsert
        RAWG와 달리 별도 API 호출 없이 게임 응답에 미디어 포함됨
        """
        media = []
        seen_rawg_ids: set[int] = set()

        for screenshot in raw.get("screenshots") or []:
            if isinstance(screenshot, dict):
                obj = GameMedia(**convert_screenshot(raw["id"], screenshot))
                if obj.rawg_id not in seen_rawg_ids:
                    seen_rawg_ids.add(obj.rawg_id)
                    media.append(obj)

        for video in raw.get("videos") or []:
            if isinstance(video, dict):
                obj = GameMedia(**convert_trailer(raw["id"], video))
                if obj.rawg_id not in seen_rawg_ids:
                    seen_rawg_ids.add(obj.rawg_id)
                    media.append(obj)

        if not media:
            return

        for m in media:
            m.game_id = game.id

        GameMedia.objects.bulk_create(
            media,
            update_conflicts=True,
            unique_fields=["game", "rawg_id"],
            update_fields=["media_url", "video_url_480", "video_url_max", "video_name"],
        )
