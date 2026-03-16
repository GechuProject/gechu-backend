"""
RawgSyncService: RAWG 데이터 → DB upsert 서비스 레이어

설계 원칙:
- 각 sync_* 메서드는 독립적으로 호출 가능
- bulk_create(update_conflicts=True)로 upsert 처리
- lookup 테이블은 페이지 단위 bulk insert (메모리 절약)
- Game sync는 페이지 단위 bulk upsert로 쿼리 수 최소화
- M2M은 through 테이블 직접 조작으로 불필요한 DELETE 방지
- is_visible은 sync 시 덮어쓰지 않음 (관리자 숨김 설정 보존)
- 서비스 레이어는 순수 비즈니스 로직만 담당 (HTTP/태스크 관심사 배제)

성능 최적화:
- Game.objects.bulk_create() → 페이지 단위 upsert
- Game.objects.in_bulk(field_name="rawg_id") → SELECT 최소화
- relation insert는 bulk_create(ignore_conflicts=True)
"""

from __future__ import annotations

import logging
from typing import Any, cast

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
from apps.games.rawg.client import RawgClient
from apps.games.rawg.converters import (
    convert_game,
    convert_genre,
    convert_platform,
    convert_screenshot,
    convert_store,
    convert_tag,
    convert_trailer,
    extract_genre_rawg_ids,
    extract_platform_entries,
    extract_store_entries,
    extract_tag_rawg_ids,
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
_STORE_UPDATE_FIELDS = ["name", "slug", "domain"]


class RawgSyncService:
    """
    RAWG API → DB 동기화 서비스

    사용 예:
        service = RawgSyncService()

        # lookup만
        service.sync_genres()

        # 게임 10페이지
        service.sync_games(max_pages=10)
    """

    def __init__(self, client: RawgClient | None = None) -> None:
        self._client = client or RawgClient()

    # 룩업 테이블 ------------------------------------------
    def sync_genres(self) -> dict[str, int]:
        """RAWG /genres → DB upsert"""

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
        """RAWG /platforms → DB upsert"""

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
        """RAWG /tags → DB upsert (중복 방지)"""

        total = 0
        seen: set[int] = set()

        for page in self._client.iter_tags():
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

        logger.info("Tag sync 완료: %d건", total)

        return {"synced": total}

    def sync_stores(self) -> dict[str, int]:
        """RAWG /stores → DB upsert"""

        total = 0

        for page in self._client.iter_stores():
            objs = [ExternalStore(**convert_store(raw)) for raw in page]

            ExternalStore.objects.bulk_create(
                objs,
                update_conflicts=True,
                unique_fields=["rawg_id"],
                update_fields=_STORE_UPDATE_FIELDS,
            )

            total += len(objs)

        logger.info("Store sync 완료: %d건", total)

        return {"synced": total}

    # Game sync ------------------------------------------
    def sync_games(
        self, ordering: str = "-added", max_pages: int | None = None, fetch_detail: bool = True
    ) -> dict[str, int]:
        """
        RAWG /games 전체 동기화

        Args:
            ordering: RAWG 정렬 기준
            max_pages: 최대 페이지 제한
            fetch_detail: 상세 API 호출 여부
        """

        total_synced = 0
        total_failed = 0
        pages = 0

        for page in self._client.iter_games(ordering=ordering):
            if max_pages and pages >= max_pages:
                break

            synced, failed = self._sync_game_page(page, fetch_detail)

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

    # Page sync------------------------------------------
    def _sync_game_page(self, page_results: list[dict[str, Any]], fetch_detail: bool) -> tuple[int, int]:
        """
        게임 목록 한 페이지 처리
        - dict 변환: RAWG API 응답 → 모델 저장용 dict (convert_game)
        - bulk_create(upsert): DB에 한 번에 저장, 쿼리 수 최소화
        - relations sync: M2M / through 테이블 관계 처리
        - media sync: 스크린샷·트레일러 등 관련 미디어 저장
        - 실패 처리: 변환·저장 실패 시 로그만 기록, 나머지는 계속 진행
        """

        games_data = []
        raw_map = {}

        for raw in page_results:
            detail = None

            try:
                if fetch_detail:
                    detail = self._client.get_game_detail(raw["id"])

                game_dict = convert_game(raw, detail)

                games_data.append(game_dict)

                raw_map[raw["id"]] = {
                    "list": raw,
                    "detail": detail,
                }

            except Exception:
                logger.exception("게임 변환 실패 rawg_id=%s", raw.get("id"))

        if not games_data:
            return 0, len(page_results)

        # Game bulk upsert

        Game.objects.bulk_create(
            [Game(**g) for g in games_data],
            update_conflicts=True,
            unique_fields=["rawg_id"],
            update_fields=_GAME_UPDATE_FIELDS,
        )

        rawg_ids = [g["rawg_id"] for g in games_data]

        games = Game.objects.in_bulk(rawg_ids, field_name="rawg_id")

        synced = 0

        for rawg_id, game in games.items():
            try:
                raw_pair = raw_map[rawg_id]

                self._sync_game_relations(game, cast(dict[str, Any], raw_pair["list"]), raw_pair["detail"])

                if raw_pair["detail"]:
                    self._sync_game_media(game)

                synced += 1

            except Exception:
                logger.exception("relation sync 실패 rawg=%s", rawg_id)

        failed = len(page_results) - synced

        return synced, failed

    # Relations ------------------------------------------
    def _sync_game_relations(self, game: Game, list_raw: dict[str, Any], detail_raw: dict[str, Any] | None) -> None:
        """
        Game M2M 관계 처리
        - 장르, 태그, 플랫폼, 스토어 관계를 bulk_create로 upsert
        - 불필요한 DELETE 방지, 관리자 설정 보존
        """

        self._sync_game_genres(game, list_raw)
        self._sync_game_tags(game, list_raw)
        self._sync_game_platforms(game, list_raw)

        if detail_raw:
            self._sync_game_stores(game, detail_raw)

    def _sync_game_genres(self, game: Game, list_raw: dict[str, Any]) -> None:

        rawg_ids = extract_genre_rawg_ids(list_raw)

        if not rawg_ids:
            return

        genre_map = {g.rawg_id: g.id for g in Genre.objects.filter(rawg_id__in=rawg_ids)}

        objs = [GameGenre(game_id=game.id, genre_id=genre_map[r]) for r in rawg_ids if r in genre_map]

        GameGenre.objects.bulk_create(objs, ignore_conflicts=True)

    def _sync_game_tags(self, game: Game, list_raw: dict[str, Any]) -> None:

        rawg_ids = extract_tag_rawg_ids(list_raw)

        if not rawg_ids:
            return

        tag_map = {t.rawg_id: t.id for t in Tag.objects.filter(rawg_id__in=rawg_ids)}

        objs = [GameTag(game_id=game.id, tag_id=tag_map[r]) for r in rawg_ids if r in tag_map]

        GameTag.objects.bulk_create(objs, ignore_conflicts=True)

    def _sync_game_platforms(self, game: Game, list_raw: dict[str, Any]) -> None:

        entries = extract_platform_entries(list_raw)

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

    def _sync_game_stores(self, game: Game, detail_raw: dict[str, Any]) -> None:

        entries = extract_store_entries(detail_raw)

        if not entries:
            return

        raw_ids = [e["store_rawg_id"] for e in entries]

        store_map = {s.rawg_id: s.id for s in ExternalStore.objects.filter(rawg_id__in=raw_ids)}

        objs = [
            GameStore(
                game_id=game.id,
                store_id=store_map[e["store_rawg_id"]],
                url=e["url"],
            )
            for e in entries
            if e["store_rawg_id"] in store_map
        ]

        GameStore.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["game", "store"],
            update_fields=["url"],
        )

    # Media ------------------------------------------
    def _sync_game_media(self, game: Game) -> None:
        """
        게임 관련 미디어 처리
        - RAWG 스크린샷/트레일러 조회
        - game_id 교체 후 bulk_create(upsert)
        - 실패 시 경고 로그만 남기고 진행
        """

        media = []

        try:
            for raw in self._client.get_game_screenshots(game.rawg_id):
                media.append(GameMedia(**convert_screenshot(game.rawg_id, raw)))
        except Exception:
            logger.warning("스크린샷 조회 실패 rawg=%s", game.rawg_id)

        try:
            for raw in self._client.get_game_trailers(game.rawg_id):
                media.append(GameMedia(**convert_trailer(game.rawg_id, raw)))
        except Exception:
            logger.warning("트레일러 조회 실패 rawg=%s", game.rawg_id)

        if not media:
            return

        for m in media:
            m.game_id = game.id

        GameMedia.objects.bulk_create(
            media,
            update_conflicts=True,
            unique_fields=["game", "rawg_id"],
            update_fields=[
                "media_url",
                "video_url_480",
                "video_url_max",
                "video_name",
            ],
        )
