import logging
from unittest.mock import MagicMock, patch

from django.test import TestCase


class SparqlQueryTest(TestCase):
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)

    @patch("apps.games.wikidata.client.requests.get")
    def test_returns_name_ko(self, mock_get: MagicMock) -> None:
        mock_get.return_value.json.return_value = {
            "results": {
                "bindings": [
                    {"igdbId": {"value": "the-witcher-3-wild-hunt"}, "nameKo": {"value": "더 위처 3"}},
                ]
            }
        }
        mock_get.return_value.raise_for_status = MagicMock()

        from apps.games.wikidata.client import sparql_query

        result = sparql_query({"the-witcher-3-wild-hunt": 1942})
        self.assertEqual(result, {1942: "더 위처 3"})

    @patch("apps.games.wikidata.client.requests.get")
    def test_network_error_returns_empty(self, mock_get: MagicMock) -> None:
        import requests as req

        mock_get.side_effect = req.RequestException("timeout")

        from apps.games.wikidata.client import sparql_query

        result = sparql_query({"the-witcher-3-wild-hunt": 1942})
        self.assertEqual(result, {})

    @patch("apps.games.wikidata.client.requests.get")
    def test_parse_error_returns_empty(self, mock_get: MagicMock) -> None:
        mock_get.return_value.json.return_value = {"unexpected": "structure"}
        mock_get.return_value.raise_for_status = MagicMock()

        from apps.games.wikidata.client import sparql_query

        result = sparql_query({"the-witcher-3-wild-hunt": 1942})
        self.assertEqual(result, {})

    @patch("apps.games.wikidata.client.requests.get")
    def test_skips_malformed_rows(self, mock_get: MagicMock) -> None:
        mock_get.return_value.json.return_value = {
            "results": {
                "bindings": [
                    {"igdbId": {"value": "invalid-slug"}, "nameKo": {"value": "이름"}},
                    {"igdbId": {"value": "the-witcher-3-wild-hunt"}, "nameKo": {"value": "더 위처 3"}},
                ]
            }
        }
        mock_get.return_value.raise_for_status = MagicMock()

        from apps.games.wikidata.client import sparql_query

        result = sparql_query({"the-witcher-3-wild-hunt": 1942})
        self.assertEqual(result, {1942: "더 위처 3"})


class GetNameKoFromCacheTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()

    def tearDown(self) -> None:
        self.r.flushdb()

    def test_pending_returns_none(self) -> None:
        from apps.games.wikidata.client import get_name_ko_from_cache

        self.assertIsNone(get_name_ko_from_cache(9999))

    def test_done_returns_name_ko(self) -> None:
        from apps.games.wikidata.client import get_name_ko_from_cache, save_name_ko

        save_name_ko(1942, "더 위처 3")
        self.assertEqual(get_name_ko_from_cache(1942), "더 위처 3")

    def test_not_found_returns_none(self) -> None:
        from apps.games.wikidata.client import get_name_ko_from_cache, save_name_ko

        save_name_ko(1942, None)
        self.assertIsNone(get_name_ko_from_cache(1942))


class SaveNameKoTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()

    def tearDown(self) -> None:
        self.r.flushdb()

    def test_saves_name_ko_and_chosung(self) -> None:
        from apps.games.wikidata.client import _hash_key, save_name_ko

        save_name_ko(1942, "더 위처 3")
        data = self.r.hgetall(_hash_key(1942))
        self.assertEqual(data[b"name_ko"], b"\xeb\x8d\x94 \xec\x9c\x84\xec\xb2\x98 3")
        self.assertIn(b"fetched_at", data)
        self.assertIn(b"chosung", data)

    def test_saves_empty_for_none(self) -> None:
        from apps.games.wikidata.client import _hash_key, save_name_ko

        save_name_ko(1942, None)
        data = self.r.hgetall(_hash_key(1942))
        self.assertEqual(data[b"name_ko"], b"")
        self.assertIn(b"fetched_at", data)


class IncrementFailedCountTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()

    def tearDown(self) -> None:
        self.r.flushdb()

    def test_increments(self) -> None:
        from apps.games.wikidata.client import get_failed_count, increment_failed_count

        self.assertEqual(increment_failed_count(1942), 1)
        self.assertEqual(increment_failed_count(1942), 2)
        self.assertEqual(get_failed_count(1942), 2)

    def test_get_failed_count_zero_when_missing(self) -> None:
        from apps.games.wikidata.client import get_failed_count

        self.assertEqual(get_failed_count(9999), 0)


class EnqueueLockTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()

    def tearDown(self) -> None:
        self.r.flushdb()

    def test_acquire_and_release(self) -> None:
        from apps.games.wikidata.client import acquire_enqueue_lock, release_enqueue_lock

        self.assertTrue(acquire_enqueue_lock(1942))
        self.assertFalse(acquire_enqueue_lock(1942))  # 이미 잠김
        release_enqueue_lock(1942)
        self.assertTrue(acquire_enqueue_lock(1942))  # 해제 후 재획득


class FetchAndSaveBulkTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()

    def tearDown(self) -> None:
        self.r.flushdb()

    @patch("apps.games.wikidata.client.sparql_query")
    def test_saves_results(self, mock_sparql: MagicMock) -> None:
        mock_sparql.return_value = {1942: "더 위처 3"}

        from apps.games.wikidata.client import fetch_and_save_bulk, get_name_ko_from_cache

        result = fetch_and_save_bulk({1942: "the-witcher-3-wild-hunt", 9999: "unknown-game"})
        self.assertEqual(result[1942], "더 위처 3")
        self.assertIsNone(result[9999])
        self.assertEqual(get_name_ko_from_cache(1942), "더 위처 3")
        self.assertIsNone(get_name_ko_from_cache(9999))
