import json
import logging
from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import TestCase


class FillNameKoCommandTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()
        logging.disable(logging.CRITICAL)

    def tearDown(self) -> None:
        self.r.flushdb()
        logging.disable(logging.NOTSET)

    def _call(self, *args: str) -> str:
        from django.core.management import call_command

        out = StringIO()
        call_command("fill_name_ko", *args, stdout=out)
        return out.getvalue()

    # fill_name_ko.py에서 이미 import된 fetch_and_save_bulk를 패치해야 함
    @patch("apps.games.management.commands.fill_name_ko.fetch_and_save_bulk")
    def test_pending_ids_processed(self, mock_bulk: MagicMock) -> None:
        mock_bulk.return_value = {1942: "더 위처 3"}

        from apps.games.wikidata.client import _hash_key

        self.r.hset(_hash_key(1942), mapping={"slug": "the-witcher-3-wild-hunt", "failed_count": "0"})

        output = self._call()
        mock_bulk.assert_called_once()
        self.assertIn("완료", output)

    @patch("apps.games.management.commands.fill_name_ko.fetch_and_save_bulk")
    @patch("apps.games.igdb.client.get_igdb_client")
    def test_specific_igdb_ids(self, mock_client: MagicMock, mock_bulk: MagicMock) -> None:
        mock_bulk.return_value = {1942: "더 위처 3", 1234: None}
        mock_get_client = MagicMock()
        mock_get_client.get_games_by_ids.return_value = [
            {"id": 1942, "slug": "the-witcher-3-wild-hunt"},
            {"id": 1234, "slug": "some-game"},
        ]
        mock_client.return_value = mock_get_client

        output = self._call("--igdb-ids", "1942,1234")
        mock_bulk.assert_called_once()
        called_ids = mock_bulk.call_args[0][0]
        self.assertIn(1942, called_ids)
        self.assertIn(1234, called_ids)
        self.assertEqual(called_ids[1942], "the-witcher-3-wild-hunt")
        self.assertEqual(called_ids[1234], "some-game")
        self.assertIn("완료", output)

    def test_no_targets_exits_early(self) -> None:
        output = self._call()
        self.assertIn("처리할 게임이 없습니다", output)

    @patch("apps.games.management.commands.fill_name_ko.fetch_and_save_bulk")
    def test_overwrite_uses_igdb_cache(self, mock_bulk: MagicMock) -> None:
        mock_bulk.return_value = {1942: "더 위처 3"}

        self.r.set("igdb:game:1942", json.dumps({"id": 1942, "slug": "the-witcher-3-wild-hunt"}))

        output = self._call("--overwrite")
        mock_bulk.assert_called_once()
        called_ids = mock_bulk.call_args[0][0]
        self.assertIn(1942, called_ids)
        self.assertEqual(called_ids[1942], "the-witcher-3-wild-hunt")
        self.assertIn("완료", output)
