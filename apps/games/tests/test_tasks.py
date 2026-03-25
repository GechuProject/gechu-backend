import logging
from unittest.mock import MagicMock, patch

from django.test import TestCase


class FetchNameKoTaskTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()
        logging.disable(logging.CRITICAL)

    def tearDown(self) -> None:
        self.r.flushdb()
        logging.disable(logging.NOTSET)

    @patch("apps.games.wikidata.client.sparql_query")
    @patch("apps.games.wikidata.client.release_enqueue_lock")
    def test_success_saves_and_releases_lock(self, mock_release: MagicMock, mock_sparql: MagicMock) -> None:
        mock_sparql.return_value = {1942: "더 위처 3"}

        from apps.games.tasks import fetch_name_ko_task
        from apps.games.wikidata.client import get_name_ko_from_cache

        fetch_name_ko_task.apply(args=(1942, "the-witcher-3-wild-hunt"))

        self.assertEqual(get_name_ko_from_cache(1942), "더 위처 3")
        mock_release.assert_called_once_with(1942)

    @patch("apps.games.wikidata.client.sparql_query")
    @patch("apps.games.wikidata.client.increment_failed_count")
    def test_sparql_failure_increments_failed_count(
        self,
        mock_increment: MagicMock,
        mock_sparql: MagicMock,
    ) -> None:
        mock_sparql.side_effect = Exception("network error")

        from apps.games.tasks import fetch_name_ko_task

        # eager 모드에서 apply()는 Retry 예외를 재시도 없이 전파
        # MaxRetriesExceededError에 도달하지 않으므로 lock 해제는 검증 불가
        result = fetch_name_ko_task.apply(args=(1942, "the-witcher-3-wild-hunt"))
        self.assertTrue(result.failed())
        mock_increment.assert_called_with(1942)


class BackfillNameKoBulkTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()
        logging.disable(logging.CRITICAL)

    def tearDown(self) -> None:
        self.r.flushdb()
        logging.disable(logging.NOTSET)

    def test_no_targets_logs_and_returns(self) -> None:
        from apps.games.tasks import backfill_name_ko_bulk

        backfill_name_ko_bulk.apply()  # 예외 없이 완료되면 OK

    @patch("apps.games.wikidata.client.fetch_and_save_bulk")
    def test_pending_ids_are_processed(self, mock_bulk: MagicMock) -> None:
        mock_bulk.return_value = {1942: "더 위처 3"}

        from apps.games.wikidata.client import _hash_key

        self.r.hset(_hash_key(1942), mapping={"slug": "the-witcher-3-wild-hunt", "failed_count": "0"})

        from apps.games.tasks import backfill_name_ko_bulk

        backfill_name_ko_bulk.apply()
        mock_bulk.assert_called_once()
        args = mock_bulk.call_args[0][0]
        self.assertIn(1942, args)
        self.assertEqual(args[1942], "the-witcher-3-wild-hunt")

    @patch("apps.games.wikidata.client.fetch_and_save_bulk")
    @patch("apps.games.wikidata.client.increment_failed_count")
    def test_not_found_increments_failed_count(self, mock_increment: MagicMock, mock_bulk: MagicMock) -> None:
        mock_bulk.return_value = {1942: None}

        from apps.games.wikidata.client import _hash_key

        self.r.hset(_hash_key(1942), mapping={"slug": "the-witcher-3-wild-hunt", "failed_count": "0"})

        from apps.games.tasks import backfill_name_ko_bulk

        backfill_name_ko_bulk.apply()
        mock_increment.assert_called_with(1942)
