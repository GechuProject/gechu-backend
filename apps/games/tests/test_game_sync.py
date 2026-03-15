from __future__ import annotations

from datetime import UTC, date
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.games.models import ExternalStore, Game, Genre, Platform, Tag
from apps.games.rawg.client import RawgClient, _build_session
from apps.games.rawg.converters import (
    _parse_esrb,
    _parse_rawg_updated,
    convert_game,
    convert_trailer,
    extract_store_entries,
)
from apps.games.rawg.exceptions import (
    RawgNotFoundError,
    RawgRateLimitError,
    RawgServerError,
)
from apps.games.services.rawg_sync import RawgSyncService


class RawgSyncServiceTestCase(TestCase):
    """RawgSyncService 단위 테스트"""

    def setUp(self) -> None:
        self.mock_client: MagicMock = MagicMock(spec=RawgClient)

        self.mock_client.iter_genres.return_value = [[{"id": 1, "name": "Action", "slug": "action"}]]
        self.mock_client.iter_platforms.return_value = [[{"id": 2, "name": "PC", "slug": "pc"}]]
        self.mock_client.iter_tags.return_value = [[{"id": 3, "name": "Multiplayer", "slug": "multiplayer"}]]
        self.mock_client.iter_stores.return_value = [[{"id": 4, "name": "Steam", "slug": "steam"}]]

        self.mock_client.iter_games.return_value = [
            [{"id": 10, "name": "Test Game", "slug": "test-game", "rating": 4.2}]
        ]
        self.mock_client.get_game_detail.return_value = {
            "description_raw": "Test description",
            "website": "https://example.com",
        }

        self.mock_client.get_game_screenshots.return_value = [{"id": 100, "image": "https://img.example.com/1.png"}]
        self.mock_client.get_game_trailers.return_value = [
            {
                "id": 200,
                "name": "Trailer 1",
                "preview": "https://img.example.com/prev.png",
                "data": {"max": "https://video.max", "data_480": "https://video.480"},
            }
        ]

        self.service: RawgSyncService = RawgSyncService(client=self.mock_client)

    def test_sync_lookup_tables(self) -> None:
        """룩업 테이블 sync 테스트"""
        genres_result = self.service.sync_genres()
        platforms_result = self.service.sync_platforms()
        tags_result = self.service.sync_tags()
        stores_result = self.service.sync_stores()

        self.assertEqual(genres_result["synced"], 1)
        self.assertEqual(platforms_result["synced"], 1)
        self.assertEqual(tags_result["synced"], 1)
        self.assertEqual(stores_result["synced"], 1)

        self.assertTrue(Genre.objects.filter(name="Action").exists())
        self.assertTrue(Platform.objects.filter(name="PC").exists())
        self.assertTrue(Tag.objects.filter(name="Multiplayer").exists())
        self.assertTrue(ExternalStore.objects.filter(name="Steam").exists())

    def test_sync_games_page(self) -> None:
        """게임 단일 페이지 sync 테스트"""
        result = self.service.sync_games(max_pages=1, fetch_detail=True)

        self.assertEqual(result["pages_processed"], 1)
        self.assertEqual(result["synced"], 1)
        self.assertEqual(result["failed"], 0)

        game: Game = Game.objects.get(rawg_id=10)
        self.assertEqual(game.name, "Test Game")
        self.assertEqual(game.description, "Test description")
        self.assertEqual(game.website, "https://example.com")

    @patch("apps.games.services.rawg_sync.RawgClient")
    def test_sync_games_with_mock_client_class(self, MockClient: MagicMock) -> None:
        mock_instance: MagicMock = MockClient.return_value
        mock_instance.iter_games.return_value = [
            [{"id": 11, "name": "Another Game", "slug": "another-game", "rating": 3.5}]
        ]
        mock_instance.get_game_detail.return_value = {"description_raw": "Another description", "website": ""}

        service: RawgSyncService = RawgSyncService(client=mock_instance)
        result = service.sync_games(max_pages=1, fetch_detail=True)

        self.assertEqual(result["synced"], 1)
        game: Game = Game.objects.get(rawg_id=11)
        self.assertEqual(game.name, "Another Game")
        self.assertEqual(game.description, "Another description")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class RawgSyncViewTestCase(TestCase):
    """RAWG Sync APIView 테스트"""

    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        self.url: str = reverse("admin-rawg-sync")
        cache.clear()

        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="password123",
            nickname="관리자",
            birth_date=date(2000, 1, 1),
        )
        self.client.force_authenticate(user=self.admin_user)

    @patch("apps.games.views.rawg_sync.sync_all_games.delay")
    @patch("apps.games.views.rawg_sync.incremental_sync.delay")
    def test_incremental_sync_post(self, mock_incremental: MagicMock, mock_sync_all: MagicMock) -> None:
        """full_sync=false → incremental_sync 호출"""
        mock_incremental.return_value = MagicMock(id="task123")

        response = self.client.post(self.url, {"full_sync": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], "pending")
        self.assertIn("job_id", response.data)
        mock_incremental.assert_called_once()
        mock_sync_all.assert_not_called()

    @patch("apps.games.views.rawg_sync.sync_all_games.delay")
    @patch("apps.games.views.rawg_sync.incremental_sync.delay")
    def test_full_sync_post(self, mock_incremental: MagicMock, mock_sync_all: MagicMock) -> None:
        """full_sync=true → sync_all_games 호출"""
        mock_sync_all.return_value = MagicMock(id="task456")

        response = self.client.post(self.url, {"full_sync": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], "pending")
        self.assertIn("job_id", response.data)
        mock_sync_all.assert_called_once()
        mock_incremental.assert_not_called()

    @patch("apps.games.views.rawg_sync.sync_all_games.delay")
    @patch("apps.games.views.rawg_sync.incremental_sync.delay")
    def test_lock_prevents_multiple_sync(self, mock_incremental: MagicMock, mock_sync_all: MagicMock) -> None:
        """이미 lock 존재 → 409 반환"""
        cache.set("rawg_sync_running", True, timeout=60)

        response = self.client.post(self.url, {"full_sync": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("이미 동기화 작업이 진행 중입니다", response.data["message"])

        mock_sync_all.assert_not_called()
        mock_incremental.assert_not_called()


class BuildSessionTestCase(TestCase):
    """_build_session 어댑터·retry  검증"""

    def test_returns_requests_session(self) -> None:
        import requests

        self.assertIsInstance(_build_session(), requests.Session)

    def test_https_adapter_mounted(self) -> None:
        from requests.adapters import HTTPAdapter

        adapter = _build_session().get_adapter("https://api.rawg.io")
        self.assertIsInstance(adapter, HTTPAdapter)

    def test_retry_excludes_429_includes_5xx(self) -> None:
        """429는 status_forcelist에 없고 5xx는 포함되어야 한다"""
        from requests.adapters import HTTPAdapter

        adapter = _build_session().get_adapter("https://api.rawg.io")
        self.assertIsInstance(adapter, HTTPAdapter)
        http_adapter: HTTPAdapter = adapter  # type: ignore[assignment]
        self.assertNotIn(429, http_adapter.max_retries.status_forcelist)
        self.assertIn(500, http_adapter.max_retries.status_forcelist)
        self.assertIn(503, http_adapter.max_retries.status_forcelist)


class RawgClientGetTestCase(TestCase):
    """_get(): 상태코드별 예외 변환"""

    def _make_client(self) -> RawgClient:
        with patch("apps.games.rawg.client.settings") as s:
            s.RAWG_API_KEY = "testkey"
            return RawgClient()

    def _mock_response(
        self,
        status_code: int,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Mock:
        resp = Mock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.headers = headers or {}
        resp.raise_for_status = Mock()
        return resp

    def test_200_returns_json(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "get", return_value=self._mock_response(200, {"count": 1})):
            self.assertEqual(client._get("games"), {"count": 1})

    def test_429_raises_rate_limit_with_retry_after(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "get", return_value=self._mock_response(429, headers={"Retry-After": "30"})):
            with self.assertRaises(RawgRateLimitError) as ctx:
                client._get("games")
        self.assertEqual(ctx.exception.retry_after, 30)

    def test_429_default_retry_after_when_header_missing(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "get", return_value=self._mock_response(429, headers={})):
            with self.assertRaises(RawgRateLimitError) as ctx:
                client._get("games")
        self.assertEqual(ctx.exception.retry_after, 60)

    def test_404_raises_not_found(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "get", return_value=self._mock_response(404)):
            with self.assertRaises(RawgNotFoundError):
                client._get("games/99999")

    def test_500_raises_server_error_with_status_code(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "get", return_value=self._mock_response(500)):
            with self.assertRaises(RawgServerError) as ctx:
                client._get("games")
        self.assertEqual(ctx.exception.status_code, 500)

    def test_503_raises_server_error(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "get", return_value=self._mock_response(503)):
            with self.assertRaises(RawgServerError):
                client._get("games")

    def test_api_key_included_in_params(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "get", return_value=self._mock_response(200, {})) as mock_get:
            client._get("games", params={"ordering": "-added"})
            _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["key"], "testkey")
        self.assertEqual(kwargs["params"]["ordering"], "-added")


class RawgClientPaginateTestCase(TestCase):
    """_paginate(): rate-limit 재시도·MAX_PAGES 방어·페이지 간 sleep"""

    def _make_client(self) -> RawgClient:
        with patch("apps.games.rawg.client.settings") as s:
            s.RAWG_API_KEY = "testkey"
            return RawgClient()

    def test_single_page_yields_results(self) -> None:
        client = self._make_client()
        with patch.object(client, "_get", return_value={"results": [{"id": 1}], "next": None}):
            pages = list(client._paginate("games"))
        self.assertEqual(pages, [[{"id": 1}]])

    def test_empty_results_stops_immediately(self) -> None:
        client = self._make_client()
        with patch.object(client, "_get", return_value={"results": [], "next": None}):
            self.assertEqual(list(client._paginate("games")), [])

    @patch("apps.games.rawg.client.logger")
    def test_rate_limit_sleeps_and_retries_successfully(self, mock_logger: MagicMock) -> None:
        """429 → Retry-After sleep → 재시도 성공 (client.py 152-155)"""
        client = self._make_client()
        ok = {"results": [{"id": 1}], "next": None}
        with patch.object(client, "_get", side_effect=[RawgRateLimitError(retry_after=2), ok]):
            with patch("apps.games.rawg.client.time.sleep") as mock_sleep:
                pages = list(client._paginate("games"))

        mock_sleep.assert_called_once_with(2)
        self.assertEqual(len(pages), 1)
        mock_logger.warning.assert_called_once()

    @patch("apps.games.rawg.client.logger")
    def test_rate_limit_reraises_on_second_failure(self, mock_logger: MagicMock) -> None:
        """재시도도 실패하면 RawgRateLimitError 그대로 raise"""
        client = self._make_client()
        with patch.object(
            client,
            "_get",
            side_effect=[RawgRateLimitError(retry_after=1), RawgRateLimitError(retry_after=1)],
        ):
            with patch("apps.games.rawg.client.time.sleep"):
                with self.assertRaises(RawgRateLimitError):
                    list(client._paginate("games"))

    @patch("apps.games.rawg.client._MAX_PAGES", 2)
    def test_max_pages_guard_stops_iteration(self) -> None:
        """_MAX_PAGES 초과 시 중단"""
        client = self._make_client()

        def _fake_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            p = (params or {}).get("page", 1)
            return {"results": [{"id": p}], "next": "http://next"}

        with patch.object(client, "_get", side_effect=_fake_get):
            with patch("apps.games.rawg.client.time.sleep"):
                with self.assertLogs("apps.games.rawg.client", level="WARNING"):
                    pages = list(client._paginate("games"))

        self.assertEqual(len(pages), 2)

    def test_page_interval_sleep_between_pages(self) -> None:
        """다음 페이지 진행 전 _PAGE_INTERVAL sleep 호출"""
        client = self._make_client()
        with patch.object(
            client,
            "_get",
            side_effect=[
                {"results": [{"id": 1}], "next": "http://next"},
                {"results": [{"id": 2}], "next": None},
            ],
        ):
            with patch("apps.games.rawg.client.time.sleep") as mock_sleep:
                list(client._paginate("games"))

        mock_sleep.assert_called_once()

    def test_multi_page_yields_all(self) -> None:
        client = self._make_client()
        with patch.object(
            client,
            "_get",
            side_effect=[
                {"results": [{"id": 1}, {"id": 2}], "next": "http://next"},
                {"results": [{"id": 3}], "next": None},
            ],
        ):
            with patch("apps.games.rawg.client.time.sleep"):
                pages = list(client._paginate("games"))

        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0], [{"id": 1}, {"id": 2}])
        self.assertEqual(pages[1], [{"id": 3}])


class RawgClientPublicInterfaceTestCase(TestCase):
    """iter_* / get_* 공개 인터페이스 라우팅 검증"""

    def _make_client(self) -> RawgClient:
        with patch("apps.games.rawg.client.settings") as s:
            s.RAWG_API_KEY = "testkey"
            return RawgClient()

    def test_iter_games_passes_params_to_paginate(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([])) as mock_paginate:
            list(client.iter_games(ordering="-added"))
        mock_paginate.assert_called_once_with("games", {"ordering": "-added"})

    def test_get_game_detail_calls_correct_path(self) -> None:
        client = self._make_client()
        with patch.object(client, "_get", return_value={"id": 3498}) as mock_get:
            result = client.get_game_detail(3498)
        mock_get.assert_called_once_with("games/3498")
        self.assertEqual(result["id"], 3498)

    def test_get_game_screenshots_collects_all_pages(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([[{"id": 1}, {"id": 2}], [{"id": 3}]])):
            self.assertEqual(client.get_game_screenshots(10), [{"id": 1}, {"id": 2}, {"id": 3}])

    def test_get_game_trailers_collects_all_pages(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([[{"id": 100}]])):
            self.assertEqual(client.get_game_trailers(10), [{"id": 100}])

    def test_iter_genres_calls_paginate_genres(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([])) as mock_paginate:
            list(client.iter_genres())
        mock_paginate.assert_called_once_with("genres")

    def test_iter_platforms_calls_paginate_platforms(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([])) as mock_paginate:
            list(client.iter_platforms())
        mock_paginate.assert_called_once_with("platforms")

    def test_iter_tags_calls_paginate_tags(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([])) as mock_paginate:
            list(client.iter_tags())
        mock_paginate.assert_called_once_with("tags")

    def test_iter_stores_calls_paginate_stores(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([])) as mock_paginate:
            list(client.iter_stores())
        mock_paginate.assert_called_once_with("stores")


class ParseEsrbTestCase(TestCase):
    def test_none_returns_unknown_zero(self) -> None:
        db_val, age = _parse_esrb(None)
        self.assertEqual(db_val, "unknown")
        self.assertEqual(age, 0)

    def test_empty_dict_returns_unknown_zero(self) -> None:
        db_val, age = _parse_esrb({})
        self.assertEqual(db_val, "unknown")
        self.assertEqual(age, 0)

    def test_everyone_slug(self) -> None:
        db_val, age = _parse_esrb({"slug": "everyone"})
        self.assertEqual(db_val, "everyone")
        self.assertEqual(age, 0)

    def test_mature_slug(self) -> None:
        db_val, age = _parse_esrb({"slug": "mature"})
        self.assertEqual(db_val, "mature")
        self.assertEqual(age, 17)

    def test_adults_only_slug(self) -> None:
        db_val, age = _parse_esrb({"slug": "adults-only"})
        self.assertEqual(db_val, "adults_only")
        self.assertEqual(age, 18)

    def test_unknown_slug_fallback(self) -> None:
        db_val, age = _parse_esrb({"slug": "not-a-real-slug"})
        self.assertEqual(db_val, "unknown")
        self.assertEqual(age, 0)


class ParseRawgUpdatedTestCase(TestCase):
    """_parse_rawg_updated: 정상·실패 케이스"""

    def test_valid_iso_z_string(self) -> None:

        result = _parse_rawg_updated({"updated": "2024-01-15T12:00:00Z"})
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.tzinfo, UTC)

    def test_missing_key_returns_none(self) -> None:
        self.assertIsNone(_parse_rawg_updated({}))

    def test_none_value_returns_none(self) -> None:
        self.assertIsNone(_parse_rawg_updated({"updated": None}))

    def test_invalid_string_returns_none(self) -> None:
        self.assertIsNone(_parse_rawg_updated({"updated": "not-a-date"}))

    def test_naive_datetime_gets_utc_tzinfo(self) -> None:

        result = _parse_rawg_updated({"updated": "2024-01-15T12:00:00"})
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.tzinfo, UTC)


class ConvertTrailerTestCase(TestCase):
    def test_full_trailer_fields(self) -> None:
        raw: dict[str, Any] = {
            "id": 200,
            "name": "Launch Trailer",
            "preview": "https://img.example.com/prev.png",
            "data": {
                "max": "https://video.example.com/max.mp4",
                "data_480": "https://video.example.com/480.mp4",
            },
        }
        result = convert_trailer(game_rawg_id=10, raw=raw)

        self.assertEqual(result["rawg_id"], 200)
        self.assertEqual(result["type"], "trailer")
        self.assertEqual(result["media_url"], "https://img.example.com/prev.png")
        self.assertEqual(result["video_url_max"], "https://video.example.com/max.mp4")
        self.assertEqual(result["video_url_480"], "https://video.example.com/480.mp4")
        self.assertEqual(result["video_name"], "Launch Trailer")
        self.assertEqual(result["game_id"], 10)

    def test_missing_data_values_are_none(self) -> None:
        raw: dict[str, Any] = {"id": 201, "name": None, "preview": "", "data": {}}
        result = convert_trailer(game_rawg_id=10, raw=raw)

        self.assertIsNone(result["video_url_max"])
        self.assertIsNone(result["video_url_480"])
        self.assertIsNone(result["video_name"])

    def test_no_data_key_at_all(self) -> None:
        """data 키 자체가 없을 때"""
        raw: dict[str, Any] = {"id": 202, "preview": "https://img.example.com/prev.png"}
        result = convert_trailer(game_rawg_id=10, raw=raw)

        self.assertIsNone(result["video_url_max"])
        self.assertIsNone(result["video_url_480"])


class ExtractStoreEntriesTestCase(TestCase):
    def test_basic_extraction(self) -> None:
        detail_raw = {
            "stores": [
                {"store": {"id": 1}, "url": "https://store.steampowered.com/app/123"},
                {"store": {"id": 3}, "url": "https://www.gog.com/game/test"},
            ]
        }
        entries = extract_store_entries(detail_raw)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["store_rawg_id"], 1)
        self.assertEqual(entries[0]["url"], "https://store.steampowered.com/app/123")

    def test_entry_without_store_id_is_skipped(self) -> None:
        detail_raw = {
            "stores": [
                {"store": {}, "url": "https://example.com"},
                {"store": {"id": 2}, "url": "https://epic.com"},
            ]
        }
        entries = extract_store_entries(detail_raw)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["store_rawg_id"], 2)

    def test_empty_stores_list(self) -> None:
        self.assertEqual(extract_store_entries({"stores": []}), [])

    def test_no_stores_key(self) -> None:
        self.assertEqual(extract_store_entries({}), [])


class ConvertGameEdgeCaseTestCase(TestCase):
    """convert_game: slug fallback, rawg_rating 상한"""

    def test_slug_fallback_when_missing(self) -> None:
        raw = {"id": 9999, "name": "NoSlug Game", "rating": 4.0}
        self.assertEqual(convert_game(raw)["slug"], "rawg-9999")

    def test_rawg_rating_capped_at_5(self) -> None:
        from decimal import Decimal

        raw = {"id": 1, "slug": "test", "name": "Test", "rating": 9.9}
        self.assertEqual(convert_game(raw)["rawg_rating"], Decimal("5.00"))

    def test_no_detail_gives_empty_description_and_website(self) -> None:
        raw = {"id": 1, "slug": "test", "name": "Test", "rating": 3.5}
        result = convert_game(raw, None)
        self.assertIsNone(result["description"])
        self.assertEqual(result["website"], "")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class SyncLookupTablesTaskTestCase(TestCase):
    """sync_lookup_tables: 성공 및 rate-limit retry"""

    def setUp(self) -> None:
        cache.clear()

    @patch("apps.games.tasks.RawgSyncService")
    def test_success_returns_all_lookup_results(self, MockService: MagicMock) -> None:
        from apps.games.tasks import sync_lookup_tables

        instance = MockService.return_value
        instance.sync_genres.return_value = {"synced": 10}
        instance.sync_platforms.return_value = {"synced": 5}
        instance.sync_tags.return_value = {"synced": 20}
        instance.sync_stores.return_value = {"synced": 3}

        result = sync_lookup_tables.apply().get()

        self.assertEqual(result["genres"]["synced"], 10)
        self.assertEqual(result["platforms"]["synced"], 5)
        self.assertEqual(result["tags"]["synced"], 20)
        self.assertEqual(result["stores"]["synced"], 3)

    @patch("apps.games.tasks.RawgSyncService")
    def test_rate_limit_triggers_retry(self, MockService: MagicMock) -> None:
        """RawgRateLimitError → self.retry(countdown=300) → Retry 예외 발생"""
        from celery.exceptions import MaxRetriesExceededError, Retry

        from apps.games.tasks import sync_lookup_tables

        instance = MockService.return_value
        instance.sync_genres.side_effect = RawgRateLimitError(retry_after=60)

        with self.assertLogs("apps.games.tasks", level="WARNING"):
            with self.assertRaises((RawgRateLimitError, MaxRetriesExceededError, Retry)):
                sync_lookup_tables.apply().get()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class SyncAllGamesTaskTestCase(TestCase):
    """sync_all_games: lock 설정/해제, rate-limit retry"""

    def setUp(self) -> None:
        cache.clear()

    @patch("apps.games.tasks.RawgSyncService")
    def test_success_clears_lock_in_finally(self, MockService: MagicMock) -> None:
        from apps.games.tasks import sync_all_games

        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 1, "synced": 5, "failed": 0}

        sync_all_games.apply(kwargs={"max_pages": 1}).get()

        self.assertIsNone(cache.get("rawg_sync_running"))

    @patch("apps.games.tasks.RawgSyncService")
    def test_rate_limit_clears_lock_and_reraises(self, MockService: MagicMock) -> None:
        """예외 발생 시에도 finally에서 lock이 해제되어야 함"""
        from celery.exceptions import MaxRetriesExceededError, Retry

        from apps.games.tasks import sync_all_games

        instance = MockService.return_value
        instance.sync_games.side_effect = RawgRateLimitError(retry_after=10)

        with self.assertLogs("apps.games.tasks", level="WARNING"):
            with self.assertRaises((RawgRateLimitError, MaxRetriesExceededError, Retry)):
                sync_all_games.apply(kwargs={"max_pages": 1}).get()
        self.assertIsNone(cache.get("rawg_sync_running"))

    @patch("apps.games.tasks.RawgSyncService")
    def test_result_contains_expected_keys(self, MockService: MagicMock) -> None:
        from apps.games.tasks import sync_all_games

        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 2, "synced": 10, "failed": 1}

        result = sync_all_games.apply(kwargs={"max_pages": 2}).get()

        self.assertIn("pages_processed", result)
        self.assertIn("synced", result)
        self.assertIn("failed", result)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class IncrementalSyncTaskTestCase(TestCase):
    """incremental_sync: lock 체크, chain 실행"""

    def setUp(self) -> None:
        cache.clear()

    @patch("apps.games.tasks.sync_all_games")
    @patch("apps.games.tasks.sync_lookup_tables")
    def test_skips_when_lock_already_set(self, mock_lookup: MagicMock, mock_games: MagicMock) -> None:
        from apps.games.tasks import incremental_sync

        cache.set("rawg_sync_running", True, timeout=60)
        incremental_sync.apply().get()

        mock_lookup.si.assert_not_called()
        mock_games.si.assert_not_called()

    @patch("apps.games.tasks.chain")
    def test_sets_lock_and_executes_chain(self, mock_chain: MagicMock) -> None:
        from apps.games.tasks import incremental_sync

        mock_chain_result = MagicMock()
        mock_chain.return_value = mock_chain_result

        incremental_sync.apply().get()

        self.assertTrue(cache.get("rawg_sync_running"))
        mock_chain.assert_called_once()
        mock_chain_result.apply_async.assert_called_once()

    @patch("apps.games.tasks.chain")
    def test_lock_is_set_before_chain_executes(self, mock_chain: MagicMock) -> None:
        """chain() 호출 시점에 이미 lock이 True여야 한다"""
        from apps.games.tasks import incremental_sync

        captured: list[Any] = []

        def capture_lock(*args: Any, **kwargs: Any) -> MagicMock:
            captured.append(cache.get("rawg_sync_running"))
            m = MagicMock()
            m.apply_async = MagicMock()
            return m

        mock_chain.side_effect = capture_lock

        incremental_sync.apply().get()

        self.assertTrue(captured[0])


class SyncRawgCommandTestCase(TestCase):
    def _run(self, *args: str, **kwargs: Any) -> str:
        out = StringIO()
        call_command("sync_rawg", *args, stdout=out, **kwargs)
        return out.getvalue()

    @patch("apps.games.management.commands.sync_rawg.RawgSyncService")
    def test_lookup_only_calls_all_four_lookup_methods(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_genres.return_value = {"synced": 1}
        instance.sync_platforms.return_value = {"synced": 2}
        instance.sync_tags.return_value = {"synced": 3}
        instance.sync_stores.return_value = {"synced": 4}

        out = self._run("--lookup-only")

        instance.sync_genres.assert_called_once()
        instance.sync_platforms.assert_called_once()
        instance.sync_tags.assert_called_once()
        instance.sync_stores.assert_called_once()
        instance.sync_games.assert_not_called()
        self.assertIn("완료", out)

    @patch("apps.games.management.commands.sync_rawg.RawgSyncService")
    def test_games_only_calls_sync_games(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 1, "synced": 5, "failed": 0}

        out = self._run("--games")

        instance.sync_games.assert_called_once()
        instance.sync_genres.assert_not_called()
        self.assertIn("완료", out)

    @patch("apps.games.management.commands.sync_rawg.RawgSyncService")
    def test_all_calls_lookup_and_games(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_genres.return_value = {"synced": 1}
        instance.sync_platforms.return_value = {"synced": 1}
        instance.sync_tags.return_value = {"synced": 1}
        instance.sync_stores.return_value = {"synced": 1}
        instance.sync_games.return_value = {"pages_processed": 1, "synced": 5, "failed": 0}

        self._run("--all")

        instance.sync_genres.assert_called_once()
        instance.sync_games.assert_called_once()

    @patch("apps.games.management.commands.sync_rawg.RawgSyncService")
    def test_max_pages_passed_to_sync_games(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 5, "synced": 25, "failed": 0}

        self._run("--games", "--max-pages", "5")

        _, call_kwargs = instance.sync_games.call_args
        self.assertEqual(call_kwargs["max_pages"], 5)

    @patch("apps.games.management.commands.sync_rawg.RawgSyncService")
    def test_ordering_passed_to_sync_games(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 1, "synced": 1, "failed": 0}

        out = StringIO()
        call_command("sync_rawg", "--games", ordering="-rating", stdout=out)

        _, call_kwargs = instance.sync_games.call_args
        self.assertEqual(call_kwargs["ordering"], "-rating")

    @patch("apps.games.management.commands.sync_rawg.RawgSyncService")
    def test_no_detail_sets_fetch_detail_false(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 1, "synced": 1, "failed": 0}

        self._run("--games", "--no-detail")

        _, call_kwargs = instance.sync_games.call_args
        self.assertFalse(call_kwargs["fetch_detail"])

    @patch("apps.games.management.commands.sync_rawg.RawgSyncService")
    def test_lookup_exception_raises_command_error(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_genres.side_effect = Exception("DB 연결 실패")

        with self.assertRaises(CommandError):
            self._run("--lookup-only")

    @patch("apps.games.management.commands.sync_rawg.RawgSyncService")
    def test_games_exception_raises_command_error(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_games.side_effect = RawgServerError("서버 오류", status_code=503)

        with self.assertRaises(CommandError):
            self._run("--games")
