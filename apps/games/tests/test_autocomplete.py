import json

from django.test import TestCase
from rest_framework.test import APIClient

from apps.games.views.autocomplete import _search
from apps.games.wikidata.client import save_name_ko


class AutocompleteViewTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.client = APIClient()
        self.r = get_redis_connection("default")
        self.r.flushdb()
        self.url = "/api/v1/games/autocomplete/"

    def tearDown(self) -> None:
        self.r.flushdb()

    def test_empty_query_returns_empty(self) -> None:
        response = self.client.get(self.url, {"q": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_no_query_param_returns_empty(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_name_ko_prefix_match(self) -> None:
        save_name_ko(1942, "더 위처 3")

        response = self.client.get(self.url, {"q": "더 위처"})
        self.assertEqual(response.status_code, 200)
        results = response.json()
        self.assertTrue(any(r["id"] == 1942 for r in results))

    def test_chosung_match(self) -> None:
        save_name_ko(1942, "더 위처 3")

        response = self.client.get(self.url, {"q": "ㄷㅇㅊ"})
        self.assertEqual(response.status_code, 200)
        results = response.json()
        self.assertTrue(any(r["id"] == 1942 for r in results))

    def test_cache_hit_returns_same_result(self) -> None:
        save_name_ko(1942, "더 위처 3")

        r1 = self.client.get(self.url, {"q": "더"}).json()
        r2 = self.client.get(self.url, {"q": "더"}).json()
        self.assertEqual(r1, r2)

    def test_no_match_returns_empty(self) -> None:
        response = self.client.get(self.url, {"q": "존재하지않는게임"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class SearchFunctionTest(TestCase):
    def setUp(self) -> None:
        from django_redis import get_redis_connection

        self.r = get_redis_connection("default")
        self.r.flushdb()

    def tearDown(self) -> None:
        self.r.flushdb()

    def test_name_ko_priority_over_chosung(self) -> None:
        save_name_ko(1942, "디아블로")  # name_ko prefix 매칭 (priority=3)
        save_name_ko(9999, "디지털 게임")  # chosung ㄷ 매칭 (priority=2)

        results = _search("디아")
        ids = [r["id"] for r in results]
        # 1942가 먼저 와야 함
        self.assertIn(1942, ids)
        if 9999 in ids:
            self.assertLess(ids.index(1942), ids.index(9999))

    def test_english_enrich_from_igdb_cache(self) -> None:
        # igdb:game:* 캐시에 영어 게임 추가
        self.r.set(
            "igdb:game:1942",
            json.dumps(
                {
                    "id": 1942,
                    "name": "Diablo IV",
                    "name_ko": "",
                    "thumbnail_img_url": "",
                }
            ),
        )

        results = _search("Diab")
        ids = [r["id"] for r in results]
        self.assertIn(1942, ids)

    def test_max_results_limit(self) -> None:
        for i in range(20):
            save_name_ko(i + 1, f"테스트게임{i}")

        results = _search("테스트")
        self.assertLessEqual(len(results), 10)
