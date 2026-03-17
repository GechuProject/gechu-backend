from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.games.igdb.cache import (
    _cache_key_game,
    _cache_key_search,
    _resolve_genre_filters,
    _resolve_platform_filters,
    _resolve_tag_filters,
    get_game_detail,
    get_games_by_ids,
    search_games,
)
from apps.games.igdb.exceptions import IgdbRateLimitError, IgdbServerError
from apps.games.models import Genre, Platform, Tag


class CacheKeyTests(TestCase):
    def test_game_key(self):
        self.assertEqual(_cache_key_game(42), "igdb:game:42")

    def test_search_key_deterministic(self):
        params = {"query": "test", "limit": 20}
        key1 = _cache_key_search(params)
        key2 = _cache_key_search(params)
        self.assertEqual(key1, key2)
        self.assertTrue(key1.startswith("igdb:search:"))

    def test_search_key_different_params(self):
        key1 = _cache_key_search({"query": "a"})
        key2 = _cache_key_search({"query": "b"})
        self.assertNotEqual(key1, key2)


class ResolveFiltersTests(TestCase):
    def test_resolve_genre_filters_empty(self):
        self.assertEqual(_resolve_genre_filters([]), {})

    def test_resolve_genre_filters(self):
        g1 = Genre.objects.create(igdb_id=99910, igdb_type="genre", name="Action-igdb-test", slug="action-igdb-test")
        g2 = Genre.objects.create(igdb_id=99920, igdb_type="theme", name="Fantasy-igdb-test", slug="fantasy-igdb-test")
        result = _resolve_genre_filters([g1.pk, g2.pk])
        self.assertEqual(result["genre"], [99910])
        self.assertEqual(result["theme"], [99920])

    def test_resolve_tag_filters_empty(self):
        self.assertEqual(_resolve_tag_filters([]), {})

    def test_resolve_tag_filters(self):
        t1 = Tag.objects.create(igdb_id=99930, igdb_type="keyword", name="Stealth-igdb-test", slug="stealth-igdb-test")
        t2 = Tag.objects.create(igdb_id=99940, igdb_type="theme", name="Horror-igdb-test", slug="horror-igdb-test")
        result = _resolve_tag_filters([t1.pk, t2.pk])
        self.assertEqual(result["keyword"], [99930])
        self.assertEqual(result["theme"], [99940])

    def test_resolve_platform_filters_empty(self):
        self.assertEqual(_resolve_platform_filters([]), [])

    def test_resolve_platform_filters(self):
        p1 = Platform.objects.create(igdb_id=9948, name="PS4-igdb-test", slug="ps4-igdb-test")
        p2 = Platform.objects.create(igdb_id=9949, name="Xbox-igdb-test", slug="xbox-one-igdb-test")
        result = _resolve_platform_filters([p1.pk, p2.pk])
        self.assertIn(9948, result)
        self.assertIn(9949, result)


class GetGameDetailTests(TestCase):
    @patch("apps.games.igdb.cache.get_igdb_client")
    @patch("apps.games.igdb.cache.cache")
    def test_returns_cached(self, mock_cache, mock_get_client):
        cached_data = {"id": 1, "name": "Cached"}
        mock_cache.get.return_value = cached_data
        result = get_game_detail(1)
        self.assertEqual(result, cached_data)
        mock_get_client.assert_not_called()

    @patch("apps.games.igdb.cache.get_igdb_client")
    @patch("apps.games.igdb.cache.cache")
    def test_fetches_and_caches(self, mock_cache, mock_get_client):
        mock_cache.get.return_value = None
        mock_client = MagicMock()
        mock_client.get_game.return_value = {
            "id": 42,
            "slug": "game",
            "name": "Game",
            "rating": 80,
            "rating_count": 10,
            "cover": {"image_id": "co1"},
        }
        mock_get_client.return_value = mock_client
        result = get_game_detail(42)
        self.assertEqual(result["id"], 42)
        mock_cache.set.assert_called_once()


class SearchGamesTests(TestCase):
    @patch("apps.games.igdb.cache.get_igdb_client")
    @patch("apps.games.igdb.cache.cache")
    def test_returns_cached(self, mock_cache, mock_get_client):
        cached_data = [{"id": 1}]
        mock_cache.get.return_value = cached_data
        result = search_games(query="test")
        self.assertEqual(result, cached_data)
        mock_get_client.assert_not_called()

    @patch("apps.games.igdb.cache._resolve_genre_filters", return_value={})
    @patch("apps.games.igdb.cache._resolve_tag_filters", return_value={})
    @patch("apps.games.igdb.cache._resolve_platform_filters", return_value=[])
    @patch("apps.games.igdb.cache.get_igdb_client")
    @patch("apps.games.igdb.cache.cache")
    def test_fetches_and_caches(self, mock_cache, mock_get_client, _rp, _rt, _rg):
        mock_cache.get.return_value = None
        mock_client = MagicMock()
        mock_client.search_games.return_value = [
            {
                "id": 10,
                "slug": "g",
                "name": "G",
                "rating": 80,
                "rating_count": 5,
                "cover": {"image_id": "co1"},
            }
        ]
        mock_get_client.return_value = mock_client
        result = search_games(query="test")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 10)
        mock_cache.set.assert_called_once()

    @patch("apps.games.igdb.cache._resolve_genre_filters", return_value={})
    @patch("apps.games.igdb.cache._resolve_tag_filters", return_value={})
    @patch("apps.games.igdb.cache._resolve_platform_filters", return_value=[])
    @patch("apps.games.igdb.cache.get_igdb_client")
    @patch("apps.games.igdb.cache.cache")
    def test_rate_limit_reraises_when_no_stale(self, mock_cache, mock_get_client, _rp, _rt, _rg):
        mock_cache.get.return_value = None
        mock_client = MagicMock()
        mock_client.search_games.side_effect = IgdbRateLimitError()
        mock_get_client.return_value = mock_client
        with self.assertRaises(IgdbRateLimitError):
            search_games(query="test")

    @patch("apps.games.igdb.cache._resolve_genre_filters", return_value={})
    @patch("apps.games.igdb.cache._resolve_tag_filters", return_value={})
    @patch("apps.games.igdb.cache._resolve_platform_filters", return_value=[])
    @patch("apps.games.igdb.cache.get_igdb_client")
    @patch("apps.games.igdb.cache.cache")
    def test_server_error_reraises_when_no_stale(self, mock_cache, mock_get_client, _rp, _rt, _rg):
        mock_cache.get.return_value = None
        mock_client = MagicMock()
        mock_client.search_games.side_effect = IgdbServerError()
        mock_get_client.return_value = mock_client
        with self.assertRaises(IgdbServerError):
            search_games(query="test")


class GetGamesByIdsTests(TestCase):
    def test_empty_ids(self):
        self.assertEqual(get_games_by_ids([]), [])

    @patch("apps.games.igdb.cache.get_igdb_client")
    @patch("apps.games.igdb.cache.cache")
    def test_all_cached(self, mock_cache, mock_get_client):
        mock_cache.get.side_effect = lambda key: {"id": 1, "name": "C"} if "1" in key else None
        result = get_games_by_ids([1])
        self.assertEqual(len(result), 1)
        mock_get_client.assert_not_called()

    @patch("apps.games.igdb.cache.get_igdb_client")
    @patch("apps.games.igdb.cache.cache")
    def test_mixed_cached_and_missing(self, mock_cache, mock_get_client):
        def cache_get(key):
            if "1" in key and "10" not in key:
                return {"id": 1, "name": "Cached"}
            return None

        mock_cache.get.side_effect = cache_get
        mock_client = MagicMock()
        mock_client.get_games_by_ids.return_value = [
            {
                "id": 10,
                "slug": "g",
                "name": "Fetched",
                "rating": 50,
                "rating_count": 5,
                "cover": {"image_id": "co1"},
            }
        ]
        mock_get_client.return_value = mock_client
        result = get_games_by_ids([1, 10])
        self.assertEqual(len(result), 2)
        mock_client.get_games_by_ids.assert_called_once_with([10])
