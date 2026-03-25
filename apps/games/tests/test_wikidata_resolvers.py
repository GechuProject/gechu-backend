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

    @patch("apps.games.wikidata.resolvers.acquire_enqueue_lock", return_value=False)
    def test_parent_game_with_edition_suffix(self, _mock: MagicMock) -> None:
        """parent_game의 한국어 이름 + 에디션 suffix 조합"""
        from apps.games.wikidata.client import save_name_ko
        from apps.games.wikidata.resolvers import resolve_name_ko

        # 부모 게임 한국어 이름 저장
        save_name_ko(119133, "젤다의 전설: 티어스 오브 더 킹덤")

        # 자식 게임 (Switch 2 Edition)
        raw = {
            "name": "The Legend of Zelda: Tears of the Kingdom - Nintendo Switch 2 Edition",
            "parent_game": 119133,
            "slug": "the-legend-of-zelda-tears-of-the-kingdom-nintendo-switch-2-edition",
        }
        result = resolve_name_ko(338073, raw)
        self.assertEqual(result, "젤다의 전설: 티어스 오브 더 킹덤 - Nintendo Switch 2 Edition")

    @patch("apps.games.wikidata.resolvers.acquire_enqueue_lock", return_value=False)
    def test_parent_game_without_suffix(self, _mock: MagicMock) -> None:
        """에디션 suffix 없으면 부모 게임 이름만 사용"""
        from apps.games.wikidata.client import save_name_ko
        from apps.games.wikidata.resolvers import resolve_name_ko

        save_name_ko(1942, "더 위처 3")

        raw = {
            "name": "The Witcher 3",
            "parent_game": 1942,
            "slug": "the-witcher-3",
        }
        result = resolve_name_ko(9999, raw)
        self.assertEqual(result, "더 위처 3")

    @patch("apps.games.wikidata.resolvers.acquire_enqueue_lock", return_value=False)
    def test_parent_game_no_korean_name(self, _mock: MagicMock) -> None:
        """부모 게임에 한국어 이름 없으면 alternative_names fallback"""
        from apps.games.wikidata.resolvers import resolve_name_ko

        raw = {
            "name": "Some Game - Deluxe Edition",
            "parent_game": 9999,
            "slug": "some-game-deluxe",
            "alternative_names": [{"name": "어떤 게임", "comment": "Korean"}],
        }
        result = resolve_name_ko(8888, raw)
        self.assertEqual(result, "어떤 게임")


class ExtractEditionSuffixTest(TestCase):
    def test_extracts_edition_with_dash(self) -> None:
        from apps.games.wikidata.resolvers import _extract_edition_suffix

        result = _extract_edition_suffix("The Legend of Zelda: Tears of the Kingdom - Nintendo Switch 2 Edition")
        self.assertEqual(result, "Nintendo Switch 2 Edition")

    def test_extracts_edition_with_colon(self) -> None:
        from apps.games.wikidata.resolvers import _extract_edition_suffix

        result = _extract_edition_suffix("Assassin's Creed II: Deluxe Edition")
        self.assertEqual(result, "Deluxe Edition")

    def test_extracts_collection(self) -> None:
        from apps.games.wikidata.resolvers import _extract_edition_suffix

        result = _extract_edition_suffix("Metal Gear Solid - The Legacy Collection")
        self.assertEqual(result, "The Legacy Collection")

    def test_no_edition_returns_empty(self) -> None:
        from apps.games.wikidata.resolvers import _extract_edition_suffix

        result = _extract_edition_suffix("The Witcher 3: Wild Hunt")
        self.assertEqual(result, "")

    def test_extracts_randomizer(self) -> None:
        from apps.games.wikidata.resolvers import _extract_edition_suffix

        result = _extract_edition_suffix("The Legend of Zelda: Tears of the Kingdom Randomizer")
        self.assertEqual(result, "Randomizer")

    def test_extracts_mod(self) -> None:
        from apps.games.wikidata.resolvers import _extract_edition_suffix

        result = _extract_edition_suffix("The Legend of Zelda: Tears of the Kingdom - Better Sages Mod")
        self.assertEqual(result, "Better Sages Mod")

    def test_false_positive_ultimate_fighting(self) -> None:
        """게임 제목에 포함된 키워드를 잘못 인식하지 않는지 테스트"""
        from apps.games.wikidata.resolvers import _extract_edition_suffix

        # 게임 제목 자체에 키워드가 있는 경우 - suffix로 인식하면 안 됨
        self.assertEqual(_extract_edition_suffix("Ultimate Fighting Championship"), "")
        self.assertEqual(_extract_edition_suffix("Dragon Ball: Sparking! Zero"), "")
        self.assertEqual(_extract_edition_suffix("Final Fantasy"), "")
        self.assertEqual(_extract_edition_suffix("Tobal 2"), "")

    def test_true_positive_with_edition_keyword(self) -> None:
        """명확한 에디션 표시가 있으면 인식해야 함"""
        from apps.games.wikidata.resolvers import _extract_edition_suffix

        self.assertEqual(
            _extract_edition_suffix("Ultimate Fighting Championship: Ultimate Edition"),
            "Ultimate Edition",
        )
        self.assertEqual(
            _extract_edition_suffix("Final Fantasy - Remastered"),
            "Remastered",
        )
        self.assertEqual(
            _extract_edition_suffix("Dragon Ball: Sparking! Zero - Deluxe Edition"),
            "Deluxe Edition",
        )
