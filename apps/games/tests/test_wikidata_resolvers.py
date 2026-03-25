from unittest.mock import MagicMock, patch

from django.test import TestCase


class ResolveNameKoTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()

    def tearDown(self) -> None:
        self.r.flushdb()

    def test_cache_hit_returns_name_ko(self) -> None:
        from apps.games.wikidata.client import save_name_ko
        from apps.games.wikidata.resolvers import resolve_name_ko

        save_name_ko(1942, "더 위처 3")
        result = resolve_name_ko(1942, {})
        self.assertEqual(result, "더 위처 3")

    @patch("apps.games.wikidata.resolvers.acquire_enqueue_lock", return_value=False)
    def test_cache_miss_falls_back_to_alt_names(self, _mock: MagicMock) -> None:
        from apps.games.wikidata.resolvers import resolve_name_ko

        raw = {
            "alternative_names": [
                {"name": "위처 3", "comment": "Korean title"},
            ]
        }
        result = resolve_name_ko(9999, raw)
        self.assertEqual(result, "위처 3")

    @patch("apps.games.wikidata.resolvers.acquire_enqueue_lock", return_value=False)
    def test_cache_miss_no_alt_names_returns_empty(self, _mock: MagicMock) -> None:
        from apps.games.wikidata.resolvers import resolve_name_ko

        result = resolve_name_ko(9999, {})
        self.assertEqual(result, "")

    @patch("apps.games.wikidata.resolvers.get_failed_count", return_value=3)
    def test_max_failed_skips_enqueue(self, _mock: MagicMock) -> None:
        from apps.games.wikidata.resolvers import _maybe_enqueue

        with patch("apps.games.wikidata.resolvers.acquire_enqueue_lock") as mock_lock:
            _maybe_enqueue(9999, "some-game-slug")
            mock_lock.assert_not_called()

    @patch("apps.games.wikidata.resolvers.get_failed_count", return_value=0)
    @patch("apps.games.wikidata.resolvers.acquire_enqueue_lock", return_value=True)
    def test_enqueue_called_when_lock_acquired(self, _mock_lock: MagicMock, _mock_count: MagicMock) -> None:
        from apps.games.wikidata.resolvers import _maybe_enqueue

        with patch("apps.games.tasks.fetch_name_ko_task") as mock_task:
            mock_task.delay = MagicMock()
            _maybe_enqueue(1942, "the-witcher-3-wild-hunt")
            mock_task.delay.assert_called_once_with(1942, "the-witcher-3-wild-hunt")
