from __future__ import annotations

from datetime import date
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

from apps.games.igdb.client import IgdbClient, _build_session, get_image_url
from apps.games.igdb.converters import (
    _parse_cover_url,
    _parse_esrb,
    _parse_rating,
    _timestamp_to_date,
    convert_game,
    convert_screenshot,
    convert_trailer,
    extract_genre_igdb_ids,
    extract_keyword_igdb_ids,
    extract_platform_entries,
    extract_store_entries,
)
from apps.games.igdb.exceptions import (
    IgdbAuthError,
    IgdbNotFoundError,
    IgdbRateLimitError,
    IgdbServerError,
)
from apps.games.igdb.service import IgdbSyncService
from apps.games.models import ExternalStore, Game, Genre, Platform, Tag


class IgdbSyncServiceTestCase(TestCase):
    """IgdbSyncService 단위 테스트"""

    def setUp(self) -> None:
        self.mock_client: MagicMock = MagicMock(spec=IgdbClient)

        self.mock_client.iter_genres.return_value = [[{"id": 1, "name": "Action", "slug": "action"}]]
        self.mock_client.iter_platforms.return_value = [[{"id": 2, "name": "PC", "slug": "pc"}]]
        self.mock_client.iter_keywords.return_value = [[{"id": 3, "name": "Multiplayer", "slug": "multiplayer"}]]
        self.mock_client.iter_games.return_value = [
            [
                {
                    "id": 10,
                    "name": "Test Game",
                    "slug": "test-game",
                    "rating": 84.0,
                    "rating_count": 100,
                    "follows": 50,
                    "updated_at": 1700000000,
                    "cover": {"image_id": "abc123"},
                    "genres": [{"id": 1}],
                    "platforms": [{"id": 2}],
                    "keywords": [{"id": 3}],
                    "screenshots": [{"id": 100, "image_id": "sc001"}],
                    "videos": [{"id": 200, "name": "Trailer 1", "video_id": "dQw4w9WgXcQ"}],
                    "websites": [{"url": "https://store.steampowered.com/app/123"}],
                }
            ]
        ]

        self.service: IgdbSyncService = IgdbSyncService(client=self.mock_client)

    def test_sync_genres(self) -> None:
        result = self.service.sync_genres()
        self.assertEqual(result["synced"], 1)
        self.assertTrue(Genre.objects.filter(name="Action").exists())

    def test_sync_platforms(self) -> None:
        result = self.service.sync_platforms()
        self.assertEqual(result["synced"], 1)
        self.assertTrue(Platform.objects.filter(name="PC").exists())

    def test_sync_tags(self) -> None:
        result = self.service.sync_tags()
        self.assertEqual(result["synced"], 1)
        self.assertTrue(Tag.objects.filter(name="Multiplayer").exists())

    def test_sync_games_page(self) -> None:
        # 룩업 테이블 먼저 생성
        Genre.objects.create(rawg_id=1, name="Action", slug="action")
        Platform.objects.create(rawg_id=2, name="PC", slug="pc")
        Tag.objects.create(rawg_id=3, name="Multiplayer", slug="multiplayer")
        ExternalStore.objects.create(rawg_id=1, name="Steam", slug="steam", domain="store.steampowered.com")

        result = self.service.sync_games(max_pages=1)

        self.assertEqual(result["pages_processed"], 1)
        self.assertEqual(result["synced"], 1)
        self.assertEqual(result["failed"], 0)

        game: Game = Game.objects.get(rawg_id=10)
        self.assertEqual(game.name, "Test Game")

    def test_sync_tags_deduplicates(self) -> None:
        """같은 rawg_id 태그 중복 방지"""
        self.mock_client.iter_keywords.return_value = [
            [
                {"id": 5, "name": "RPG", "slug": "rpg"},
                {"id": 5, "name": "RPG", "slug": "rpg"},  # 중복
            ]
        ]
        result = self.service.sync_tags()
        self.assertEqual(result["synced"], 1)
        self.assertEqual(Tag.objects.filter(rawg_id=5).count(), 1)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class IgdbSyncViewTestCase(TestCase):
    """IGDB Sync APIView 테스트"""

    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        self.url: str = reverse("admin-igdb-sync")
        cache.clear()

        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="password123",
            nickname="관리자",
            birth_date=date(2000, 1, 1),
        )
        self.client.force_authenticate(user=self.admin_user)

    @patch("apps.games.igdb.views.sync_all_games.delay")
    @patch("apps.games.igdb.views.incremental_sync.delay")
    def test_incremental_sync_post(self, mock_incremental: MagicMock, mock_sync_all: MagicMock) -> None:
        """full_sync=false → incremental_sync 호출"""
        mock_incremental.return_value = MagicMock(id="task123")

        response = self.client.post(self.url, {"full_sync": False}, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["status"], "pending")
        self.assertIn("job_id", response.data)
        mock_incremental.assert_called_once()
        mock_sync_all.assert_not_called()

    @patch("apps.games.igdb.views.sync_all_games.delay")
    @patch("apps.games.igdb.views.incremental_sync.delay")
    def test_full_sync_post(self, mock_incremental: MagicMock, mock_sync_all: MagicMock) -> None:
        """full_sync=true → sync_all_games 호출"""
        mock_sync_all.return_value = MagicMock(id="task456")

        response = self.client.post(self.url, {"full_sync": True}, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mock_sync_all.assert_called_once()
        mock_incremental.assert_not_called()

    @patch("apps.games.igdb.views.sync_all_games.delay")
    @patch("apps.games.igdb.views.incremental_sync.delay")
    def test_lock_prevents_multiple_sync(self, mock_incremental: MagicMock, mock_sync_all: MagicMock) -> None:
        """이미 lock 존재 → 409 반환"""
        cache.set("igdb_sync_running", True, timeout=60)

        response = self.client.post(self.url, {"full_sync": True}, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("이미 동기화 작업이 진행 중입니다", response.data["message"])
        mock_sync_all.assert_not_called()
        mock_incremental.assert_not_called()

    def test_unauthenticated_returns_401(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url, {"full_sync": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class BuildSessionTestCase(TestCase):
    """_build_session: 어댑터·retry 설정 검증"""

    def test_returns_requests_session(self) -> None:
        import requests

        self.assertIsInstance(_build_session(), requests.Session)

    def test_https_adapter_mounted(self) -> None:
        from requests.adapters import HTTPAdapter

        adapter = _build_session().get_adapter("https://api.igdb.com")
        self.assertIsInstance(adapter, HTTPAdapter)

    def test_retry_excludes_429_includes_5xx(self) -> None:
        from requests.adapters import HTTPAdapter

        adapter = _build_session().get_adapter("https://api.igdb.com")
        self.assertIsInstance(adapter, HTTPAdapter)
        http_adapter: HTTPAdapter = adapter  # type: ignore[assignment]
        self.assertNotIn(429, http_adapter.max_retries.status_forcelist)
        self.assertIn(500, http_adapter.max_retries.status_forcelist)
        self.assertIn(503, http_adapter.max_retries.status_forcelist)


class GetImageUrlTestCase(TestCase):
    """get_image_url: URL 조합 검증"""

    def test_default_size(self) -> None:
        url = get_image_url("abc123")
        self.assertEqual(url, "https://images.igdb.com/igdb/image/upload/t_cover_big/abc123.jpg")

    def test_custom_size(self) -> None:
        url = get_image_url("abc123", "screenshot_big")
        self.assertIn("t_screenshot_big", url)
        self.assertIn("abc123.jpg", url)


class IgdbClientPostTestCase(TestCase):
    """_post(): 상태코드별 예외 변환"""

    def _make_client(self) -> IgdbClient:
        with patch("apps.games.igdb.client.settings") as s:
            s.IGDB_CLIENT_ID = "test_client_id"
            s.IGDB_CLIENT_SECRET = "test_secret"
            with patch.object(IgdbClient, "_fetch_token", return_value="test_token"):
                return IgdbClient()

    def _mock_response(
        self,
        status_code: int,
        json_data: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Mock:
        resp = Mock()
        resp.status_code = status_code
        resp.json.return_value = json_data or []
        resp.headers = headers or {}
        resp.raise_for_status = Mock()
        return resp

    def test_200_returns_list(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "post", return_value=self._mock_response(200, [{"id": 1}])):
            result = client._post("games", "fields id;")
        self.assertEqual(result, [{"id": 1}])

    def test_401_raises_auth_error(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "post", return_value=self._mock_response(401)):
            with self.assertRaises(IgdbAuthError):
                client._post("games", "fields id;")

    def test_429_raises_rate_limit_with_retry_after(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "post", return_value=self._mock_response(429, headers={"Retry-After": "2"})):
            with self.assertRaises(IgdbRateLimitError) as ctx:
                client._post("games", "fields id;")
        self.assertEqual(ctx.exception.retry_after, 2)

    def test_429_default_retry_after_when_header_missing(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "post", return_value=self._mock_response(429, headers={})):
            with self.assertRaises(IgdbRateLimitError) as ctx:
                client._post("games", "fields id;")
        self.assertEqual(ctx.exception.retry_after, 1)

    def test_404_raises_not_found(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "post", return_value=self._mock_response(404)):
            with self.assertRaises(IgdbNotFoundError):
                client._post("games", "fields id;")

    def test_500_raises_server_error(self) -> None:
        client = self._make_client()
        with patch.object(client._session, "post", return_value=self._mock_response(500)):
            with self.assertRaises(IgdbServerError) as ctx:
                client._post("games", "fields id;")
        self.assertEqual(ctx.exception.status_code, 500)


class IgdbClientAuthRetryTestCase(TestCase):
    """_post_with_auth_retry: 401 발생 시 토큰 재발급 후 재시도"""

    def _make_client(self) -> IgdbClient:
        with patch("apps.games.igdb.client.settings") as s:
            s.IGDB_CLIENT_ID = "test_client_id"
            s.IGDB_CLIENT_SECRET = "test_secret"
            with patch.object(IgdbClient, "_fetch_token", return_value="test_token"):
                return IgdbClient()

    @patch("apps.games.igdb.client.logger")
    def test_retries_on_auth_error(self, mock_logger: MagicMock) -> None:
        client = self._make_client()
        ok_result = [{"id": 1}]
        with patch.object(client, "_post", side_effect=[IgdbAuthError(), ok_result]):
            with patch.object(client, "_fetch_token", return_value="new_token"):
                result = client._post_with_auth_retry("games", "fields id;")
        self.assertEqual(result, ok_result)
        self.assertEqual(client._access_token, "new_token")
        mock_logger.warning.assert_called_once()


class IgdbClientPaginateTestCase(TestCase):
    """_paginate(): rate-limit 재시도·MAX_PAGES 방어·페이지 간 sleep"""

    def _make_client(self) -> IgdbClient:
        with patch("apps.games.igdb.client.settings") as s:
            s.IGDB_CLIENT_ID = "test_client_id"
            s.IGDB_CLIENT_SECRET = "test_secret"
            with patch.object(IgdbClient, "_fetch_token", return_value="test_token"):
                return IgdbClient()

    def test_single_page_yields_results(self) -> None:
        client = self._make_client()
        with patch.object(client, "_post_with_auth_retry", return_value=[{"id": 1}]):
            pages = list(client._paginate("games", "id,name"))
        self.assertEqual(pages, [[{"id": 1}]])

    def test_empty_results_stops_immediately(self) -> None:
        client = self._make_client()
        with patch.object(client, "_post_with_auth_retry", return_value=[]):
            self.assertEqual(list(client._paginate("games", "id,name")), [])

    @patch("apps.games.igdb.client.logger")
    def test_rate_limit_sleeps_and_retries_successfully(self, mock_logger: MagicMock) -> None:
        client = self._make_client()
        ok = [{"id": 1}]
        with patch.object(client, "_post_with_auth_retry", side_effect=[IgdbRateLimitError(retry_after=2), ok]):
            with patch("apps.games.igdb.client.time.sleep") as mock_sleep:
                pages = list(client._paginate("games", "id,name"))

        mock_sleep.assert_called_once_with(2)
        self.assertEqual(len(pages), 1)
        mock_logger.warning.assert_called_once()

    @patch("apps.games.igdb.client.logger")
    def test_rate_limit_reraises_on_second_failure(self, mock_logger: MagicMock) -> None:
        client = self._make_client()
        with patch.object(
            client,
            "_post_with_auth_retry",
            side_effect=[IgdbRateLimitError(retry_after=1), IgdbRateLimitError(retry_after=1)],
        ):
            with patch("apps.games.igdb.client.time.sleep"):
                with self.assertRaises(IgdbRateLimitError):
                    list(client._paginate("games", "id,name"))

    @patch("apps.games.igdb.client._MAX_PAGES", 2)
    def test_max_pages_guard_stops_iteration(self) -> None:
        client = self._make_client()

        # PAGE_SIZE보다 많은 결과를 반환해서 다음 페이지로 넘어가게 함
        full_page = [{"id": i} for i in range(500)]

        with patch.object(client, "_post_with_auth_retry", return_value=full_page):
            with patch("apps.games.igdb.client.time.sleep"):
                with self.assertLogs("apps.games.igdb.client", level="WARNING"):
                    pages = list(client._paginate("games", "id,name"))

        self.assertEqual(len(pages), 2)

    def test_page_interval_sleep_between_pages(self) -> None:
        client = self._make_client()
        full_page = [{"id": i} for i in range(500)]
        small_page = [{"id": 999}]

        with patch.object(client, "_post_with_auth_retry", side_effect=[full_page, small_page]):
            with patch("apps.games.igdb.client.time.sleep") as mock_sleep:
                list(client._paginate("games", "id,name"))

        mock_sleep.assert_called_once()

    def test_stops_when_results_less_than_page_size(self) -> None:
        """결과가 PAGE_SIZE보다 적으면 마지막 페이지로 판단하고 중단"""
        client = self._make_client()
        with patch.object(
            client,
            "_post_with_auth_retry",
            return_value=[{"id": 1}, {"id": 2}],  # PAGE_SIZE(500)보다 적음
        ):
            pages = list(client._paginate("games", "id,name"))

        self.assertEqual(len(pages), 1)


class IgdbClientPublicInterfaceTestCase(TestCase):
    """iter_* / get_* 공개 인터페이스 라우팅 검증"""

    def _make_client(self) -> IgdbClient:
        with patch("apps.games.igdb.client.settings") as s:
            s.IGDB_CLIENT_ID = "test_client_id"
            s.IGDB_CLIENT_SECRET = "test_secret"
            with patch.object(IgdbClient, "_fetch_token", return_value="test_token"):
                return IgdbClient()

    def test_iter_games_calls_paginate(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([])) as mock_paginate:
            list(client.iter_games())
        mock_paginate.assert_called_once()
        args = mock_paginate.call_args[0]
        self.assertEqual(args[0], "games")

    def test_get_game_returns_first_result(self) -> None:
        client = self._make_client()
        with patch.object(client, "_post_with_auth_retry", return_value=[{"id": 1942, "name": "GTA V"}]):
            result = client.get_game(1942)
        self.assertEqual(result["id"], 1942)

    def test_get_game_raises_not_found_when_empty(self) -> None:
        client = self._make_client()
        with patch.object(client, "_post_with_auth_retry", return_value=[]):
            with self.assertRaises(IgdbNotFoundError):
                client.get_game(99999)

    def test_iter_genres_calls_paginate_genres(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([])) as mock_paginate:
            list(client.iter_genres())
        args = mock_paginate.call_args[0]
        self.assertEqual(args[0], "genres")

    def test_iter_platforms_calls_paginate_platforms(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([])) as mock_paginate:
            list(client.iter_platforms())
        args = mock_paginate.call_args[0]
        self.assertEqual(args[0], "platforms")

    def test_iter_keywords_calls_paginate_keywords(self) -> None:
        client = self._make_client()
        with patch.object(client, "_paginate", return_value=iter([])) as mock_paginate:
            list(client.iter_keywords())
        args = mock_paginate.call_args[0]
        self.assertEqual(args[0], "keywords")


class TimestampToDateTestCase(TestCase):
    """_timestamp_to_date: Unix timestamp → date 변환"""

    def test_valid_timestamp(self) -> None:
        result = _timestamp_to_date(1700000000)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsInstance(result, date)

    def test_none_returns_none(self) -> None:
        self.assertIsNone(_timestamp_to_date(None))

    def test_zero_returns_none(self) -> None:
        self.assertIsNone(_timestamp_to_date(0))


class ParseEsrbTestCase(TestCase):
    """_parse_esrb: IGDB age_ratings 배열 파싱"""

    def test_none_returns_unknown(self) -> None:
        db_val, age = _parse_esrb(None)
        self.assertEqual(db_val, "unknown")
        self.assertEqual(age, 0)

    def test_empty_list_returns_unknown(self) -> None:
        db_val, age = _parse_esrb([])
        self.assertEqual(db_val, "unknown")
        self.assertEqual(age, 0)

    def test_esrb_mature(self) -> None:
        db_val, age = _parse_esrb([{"category": 1, "rating": 6}])
        self.assertEqual(db_val, "mature")
        self.assertEqual(age, 17)

    def test_esrb_everyone(self) -> None:
        db_val, age = _parse_esrb([{"category": 1, "rating": 3}])
        self.assertEqual(db_val, "everyone")
        self.assertEqual(age, 0)

    def test_esrb_everyone_10_plus(self) -> None:
        db_val, age = _parse_esrb([{"category": 1, "rating": 4}])
        self.assertEqual(db_val, "everyone_10_plus")
        self.assertEqual(age, 10)

    def test_esrb_adults_only(self) -> None:
        db_val, age = _parse_esrb([{"category": 1, "rating": 7}])
        self.assertEqual(db_val, "adults_only")
        self.assertEqual(age, 18)

    def test_pegi_only_returns_unknown(self) -> None:
        """ESRB(category=1)가 없고 PEGI(category=2)만 있으면 unknown"""
        db_val, age = _parse_esrb([{"category": 2, "rating": 3}])
        self.assertEqual(db_val, "unknown")
        self.assertEqual(age, 0)

    def test_non_dict_items_skipped(self) -> None:
        db_val, age = _parse_esrb(["not_a_dict"])  # type: ignore[list-item]
        self.assertEqual(db_val, "unknown")


class ParseRatingTestCase(TestCase):
    """_parse_rating: IGDB 0~100 → 0~5 변환"""

    def test_none_returns_zero(self) -> None:
        from decimal import Decimal

        self.assertEqual(_parse_rating(None), Decimal("0.00"))

    def test_100_becomes_5(self) -> None:
        from decimal import Decimal

        self.assertEqual(_parse_rating(100), Decimal("5.00"))

    def test_80_becomes_4(self) -> None:
        from decimal import Decimal

        self.assertEqual(_parse_rating(80), Decimal("4.00"))

    def test_over_100_capped_at_5(self) -> None:
        from decimal import Decimal

        self.assertEqual(_parse_rating(120), Decimal("5.00"))

    def test_zero_returns_zero(self) -> None:
        from decimal import Decimal

        self.assertEqual(_parse_rating(0), Decimal("0.00"))


class ParseCoverUrlTestCase(TestCase):
    """_parse_cover_url: cover 객체 → URL"""

    def test_valid_cover(self) -> None:
        result = _parse_cover_url({"image_id": "abc123"})
        self.assertIn("abc123", result)
        self.assertIn("cover_big", result)

    def test_none_returns_empty(self) -> None:
        self.assertEqual(_parse_cover_url(None), "")

    def test_missing_image_id_returns_empty(self) -> None:
        self.assertEqual(_parse_cover_url({}), "")


class ConvertGameTestCase(TestCase):
    """convert_game: IGDB raw → Game 모델 dict"""

    def test_basic_conversion(self) -> None:
        from decimal import Decimal

        raw: dict[str, Any] = {
            "id": 1942,
            "name": "GTA V",
            "slug": "grand-theft-auto-v",
            "summary": "Open world game",
            "rating": 80.0,
            "rating_count": 500,
            "follows": 10000,
            "updated_at": 1700000000,
            "cover": {"image_id": "cover001"},
        }
        result = convert_game(raw)

        self.assertEqual(result["rawg_id"], 1942)
        self.assertEqual(result["name"], "GTA V")
        self.assertEqual(result["slug"], "grand-theft-auto-v")
        self.assertEqual(result["description"], "Open world game")
        self.assertEqual(result["rawg_rating"], Decimal("4.00"))
        self.assertIn("cover001", result["thumbnail_img_url"])

    def test_slug_fallback_when_missing(self) -> None:
        raw: dict[str, Any] = {"id": 9999, "name": "No Slug Game", "updated_at": 1700000000}
        result = convert_game(raw)
        self.assertEqual(result["slug"], "igdb-9999")

    def test_storyline_used_when_summary_missing(self) -> None:
        raw: dict[str, Any] = {
            "id": 1,
            "name": "Test",
            "storyline": "Epic story",
            "updated_at": 1700000000,
        }
        result = convert_game(raw)
        self.assertEqual(result["description"], "Epic story")

    def test_tba_always_false(self) -> None:
        raw: dict[str, Any] = {"id": 1, "name": "Test", "updated_at": 1700000000}
        self.assertFalse(convert_game(raw)["tba"])

    def test_metacritic_always_none(self) -> None:
        raw: dict[str, Any] = {"id": 1, "name": "Test", "updated_at": 1700000000}
        self.assertIsNone(convert_game(raw)["metacritic"])


class ExtractGenreIgdbIdsTestCase(TestCase):
    """extract_genre_igdb_ids"""

    def test_basic_extraction(self) -> None:
        raw: dict[str, Any] = {"genres": [{"id": 1}, {"id": 5}]}
        self.assertEqual(extract_genre_igdb_ids(raw), [1, 5])

    def test_missing_key_returns_empty(self) -> None:
        self.assertEqual(extract_genre_igdb_ids({}), [])

    def test_non_dict_items_skipped(self) -> None:
        raw: dict[str, Any] = {"genres": [{"id": 1}, "invalid"]}
        self.assertEqual(extract_genre_igdb_ids(raw), [1])


class ExtractKeywordIgdbIdsTestCase(TestCase):
    """extract_keyword_igdb_ids"""

    def test_basic_extraction(self) -> None:
        raw: dict[str, Any] = {"keywords": [{"id": 10}, {"id": 20}]}
        self.assertEqual(extract_keyword_igdb_ids(raw), [10, 20])

    def test_empty_keywords(self) -> None:
        self.assertEqual(extract_keyword_igdb_ids({"keywords": []}), [])


class ExtractPlatformEntriesTestCase(TestCase):
    """extract_platform_entries"""

    def test_basic_extraction(self) -> None:
        raw: dict[str, Any] = {"platforms": [{"id": 6}, {"id": 48}]}
        entries = extract_platform_entries(raw)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["platform_rawg_id"], 6)
        self.assertEqual(entries[0]["requirements_minimum"], "")
        self.assertEqual(entries[0]["requirements_recommended"], "")

    def test_missing_id_skipped(self) -> None:
        raw: dict[str, Any] = {"platforms": [{}, {"id": 6}]}
        entries = extract_platform_entries(raw)
        self.assertEqual(len(entries), 1)


class ExtractStoreEntriesTestCase(TestCase):
    """extract_store_entries: URL 패턴 기반 스토어 매칭"""

    def test_steam_url_matched(self) -> None:
        raw: dict[str, Any] = {"websites": [{"url": "https://store.steampowered.com/app/730"}]}
        entries = extract_store_entries(raw)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["store_slug"], "steam")
        self.assertEqual(entries[0]["url"], "https://store.steampowered.com/app/730")

    def test_epic_url_matched(self) -> None:
        raw: dict[str, Any] = {"websites": [{"url": "https://www.epicgames.com/store/product/test"}]}
        entries = extract_store_entries(raw)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["store_slug"], "epic-games")

    def test_non_store_url_skipped(self) -> None:
        raw: dict[str, Any] = {"websites": [{"url": "https://twitter.com/test"}]}
        self.assertEqual(extract_store_entries(raw), [])

    def test_empty_websites(self) -> None:
        self.assertEqual(extract_store_entries({"websites": []}), [])

    def test_no_websites_key(self) -> None:
        self.assertEqual(extract_store_entries({}), [])

    def test_multiple_stores(self) -> None:
        raw: dict[str, Any] = {
            "websites": [
                {"url": "https://store.steampowered.com/app/730"},
                {"url": "https://www.gog.com/game/test"},
            ]
        }
        entries = extract_store_entries(raw)
        self.assertEqual(len(entries), 2)
        slugs = {e["store_slug"] for e in entries}
        self.assertIn("steam", slugs)
        self.assertIn("gog", slugs)


class ConvertScreenshotTestCase(TestCase):
    """convert_screenshot: IGDB screenshot → GameMedia dict"""

    def test_basic_conversion(self) -> None:
        raw: dict[str, Any] = {"id": 100, "image_id": "sc001"}
        result = convert_screenshot(game_igdb_id=10, raw=raw)

        self.assertEqual(result["rawg_id"], 100)
        self.assertEqual(result["type"], "screenshot")
        self.assertIn("sc001", result["media_url"])
        self.assertIn("screenshot_big", result["media_url"])
        self.assertIsNone(result["video_url_480"])
        self.assertIsNone(result["video_url_max"])
        self.assertEqual(result["game_id"], 10)

    def test_missing_image_id(self) -> None:
        raw: dict[str, Any] = {"id": 101}
        result = convert_screenshot(game_igdb_id=10, raw=raw)
        self.assertEqual(result["media_url"], "")


class ConvertTrailerTestCase(TestCase):
    """convert_trailer: IGDB video → GameMedia dict (YouTube URL 조합)"""

    def test_full_trailer_fields(self) -> None:
        raw: dict[str, Any] = {"id": 200, "name": "Launch Trailer", "video_id": "dQw4w9WgXcQ"}
        result = convert_trailer(game_igdb_id=10, raw=raw)

        self.assertEqual(result["rawg_id"], 200)
        self.assertEqual(result["type"], "trailer")
        self.assertEqual(result["video_name"], "Launch Trailer")
        self.assertEqual(result["game_id"], 10)
        self.assertIn("dQw4w9WgXcQ", result["media_url"])
        self.assertIn("dQw4w9WgXcQ", result["video_url_480"])
        self.assertIn("dQw4w9WgXcQ", result["video_url_max"])
        self.assertIn("embed", result["video_url_480"])
        self.assertIn("watch", result["video_url_max"])

    def test_missing_video_id(self) -> None:
        raw: dict[str, Any] = {"id": 201, "name": None}
        result = convert_trailer(game_igdb_id=10, raw=raw)

        self.assertEqual(result["media_url"], "")
        self.assertIsNone(result["video_url_480"])
        self.assertIsNone(result["video_url_max"])
        self.assertIsNone(result["video_name"])


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class IgdbSyncLookupTablesTaskTestCase(TestCase):
    """sync_lookup_tables: 성공 및 rate-limit retry"""

    def setUp(self) -> None:
        cache.clear()

    @patch("apps.games.igdb.tasks.IgdbSyncService")
    def test_success_returns_all_lookup_results(self, MockService: MagicMock) -> None:
        from apps.games.igdb.tasks import sync_lookup_tables

        instance = MockService.return_value
        instance.sync_genres.return_value = {"synced": 23}
        instance.sync_platforms.return_value = {"synced": 220}
        instance.sync_tags.return_value = {"synced": 6927}

        result = sync_lookup_tables.apply().get()

        self.assertEqual(result["genres"]["synced"], 23)
        self.assertEqual(result["platforms"]["synced"], 220)
        self.assertEqual(result["tags"]["synced"], 6927)

    @patch("apps.games.igdb.tasks.IgdbSyncService")
    def test_rate_limit_triggers_retry(self, MockService: MagicMock) -> None:
        from celery.exceptions import MaxRetriesExceededError, Retry

        from apps.games.igdb.tasks import sync_lookup_tables

        instance = MockService.return_value
        instance.sync_genres.side_effect = IgdbRateLimitError(retry_after=1)

        with self.assertLogs("apps.games.igdb.tasks", level="WARNING"):
            with self.assertRaises((IgdbRateLimitError, MaxRetriesExceededError, Retry)):
                sync_lookup_tables.apply().get()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class IgdbSyncAllGamesTaskTestCase(TestCase):
    """sync_all_games: lock 설정/해제, rate-limit retry"""

    def setUp(self) -> None:
        cache.clear()

    @patch("apps.games.igdb.tasks.IgdbSyncService")
    def test_success_clears_lock_in_finally(self, MockService: MagicMock) -> None:
        from apps.games.igdb.tasks import sync_all_games

        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 1, "synced": 5, "failed": 0}

        sync_all_games.apply(kwargs={"max_pages": 1}).get()

        self.assertIsNone(cache.get("igdb_sync_running"))

    @patch("apps.games.igdb.tasks.IgdbSyncService")
    def test_rate_limit_clears_lock_and_reraises(self, MockService: MagicMock) -> None:
        from celery.exceptions import MaxRetriesExceededError, Retry

        from apps.games.igdb.tasks import sync_all_games

        instance = MockService.return_value
        instance.sync_games.side_effect = IgdbRateLimitError(retry_after=1)

        with self.assertLogs("apps.games.igdb.tasks", level="WARNING"):
            with self.assertRaises((IgdbRateLimitError, MaxRetriesExceededError, Retry)):
                sync_all_games.apply(kwargs={"max_pages": 1}).get()

        self.assertIsNone(cache.get("igdb_sync_running"))

    @patch("apps.games.igdb.tasks.IgdbSyncService")
    def test_result_contains_expected_keys(self, MockService: MagicMock) -> None:
        from apps.games.igdb.tasks import sync_all_games

        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 2, "synced": 10, "failed": 0}

        result = sync_all_games.apply(kwargs={"max_pages": 2}).get()

        self.assertIn("pages_processed", result)
        self.assertIn("synced", result)
        self.assertIn("failed", result)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class IgdbIncrementalSyncTaskTestCase(TestCase):
    """incremental_sync: lock 체크, chain 실행"""

    def setUp(self) -> None:
        cache.clear()

    @patch("apps.games.igdb.tasks.sync_all_games")
    @patch("apps.games.igdb.tasks.sync_lookup_tables")
    def test_skips_when_lock_already_set(self, mock_lookup: MagicMock, mock_games: MagicMock) -> None:
        from apps.games.igdb.tasks import incremental_sync

        cache.set("igdb_sync_running", True, timeout=60)
        incremental_sync.apply().get()

        mock_lookup.si.assert_not_called()
        mock_games.si.assert_not_called()

    @patch("apps.games.igdb.tasks.chain")
    def test_sets_lock_and_executes_chain(self, mock_chain: MagicMock) -> None:
        from apps.games.igdb.tasks import incremental_sync

        mock_chain_result = MagicMock()
        mock_chain.return_value = mock_chain_result

        incremental_sync.apply().get()

        self.assertTrue(cache.get("igdb_sync_running"))
        mock_chain.assert_called_once()
        mock_chain_result.apply_async.assert_called_once()

    @patch("apps.games.igdb.tasks.chain")
    def test_lock_is_set_before_chain_executes(self, mock_chain: MagicMock) -> None:
        from apps.games.igdb.tasks import incremental_sync

        captured: list[Any] = []

        def capture_lock(*args: Any, **kwargs: Any) -> MagicMock:
            captured.append(cache.get("igdb_sync_running"))
            m = MagicMock()
            m.apply_async = MagicMock()
            return m

        mock_chain.side_effect = capture_lock
        incremental_sync.apply().get()

        self.assertTrue(captured[0])


class SyncIgdbCommandTestCase(TestCase):
    """management command sync_igdb 전체 커버"""

    def _run(self, *args: str, **kwargs: Any) -> str:
        out = StringIO()
        call_command("sync_igdb", *args, stdout=out, **kwargs)
        return out.getvalue()

    @patch("apps.games.management.commands.sync_igdb.IgdbSyncService")
    def test_lookup_only_calls_all_three_lookup_methods(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_genres.return_value = {"synced": 23}
        instance.sync_platforms.return_value = {"synced": 220}
        instance.sync_tags.return_value = {"synced": 6927}

        out = self._run("--lookup-only")

        instance.sync_genres.assert_called_once()
        instance.sync_platforms.assert_called_once()
        instance.sync_tags.assert_called_once()
        instance.sync_games.assert_not_called()
        self.assertIn("완료", out)

    @patch("apps.games.management.commands.sync_igdb.IgdbSyncService")
    def test_games_only_calls_sync_games(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 1, "synced": 500, "failed": 0}

        out = self._run("--games")

        instance.sync_games.assert_called_once()
        instance.sync_genres.assert_not_called()
        self.assertIn("완료", out)

    @patch("apps.games.management.commands.sync_igdb.IgdbSyncService")
    def test_all_calls_lookup_then_games(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_genres.return_value = {"synced": 23}
        instance.sync_platforms.return_value = {"synced": 220}
        instance.sync_tags.return_value = {"synced": 6927}
        instance.sync_games.return_value = {"pages_processed": 1, "synced": 500, "failed": 0}

        self._run("--all")

        instance.sync_genres.assert_called_once()
        instance.sync_games.assert_called_once()

    @patch("apps.games.management.commands.sync_igdb.IgdbSyncService")
    def test_max_pages_passed_to_sync_games(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_games.return_value = {"pages_processed": 3, "synced": 1500, "failed": 0}

        self._run("--games", "--max-pages", "3")

        _, call_kwargs = instance.sync_games.call_args
        self.assertEqual(call_kwargs["max_pages"], 3)

    @patch("apps.games.management.commands.sync_igdb.IgdbSyncService")
    def test_lookup_exception_raises_command_error(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_genres.side_effect = Exception("연결 실패")

        with self.assertRaises(CommandError):
            self._run("--lookup-only")

    @patch("apps.games.management.commands.sync_igdb.IgdbSyncService")
    def test_games_exception_raises_command_error(self, MockService: MagicMock) -> None:
        instance = MockService.return_value
        instance.sync_games.side_effect = IgdbServerError("서버 오류", status_code=503)

        with self.assertRaises(CommandError):
            self._run("--games")
