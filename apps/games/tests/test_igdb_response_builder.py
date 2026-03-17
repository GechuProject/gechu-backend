from decimal import Decimal

from django.test import TestCase

from apps.games.igdb.response_builder import (
    build_game_detail,
    build_game_list_item,
    build_similar_game_item,
)


class BuildGameListItemTests(TestCase):
    def _make_raw(self, **overrides):
        base = {
            "id": 1942,
            "slug": "the-witcher-3",
            "name": "The Witcher 3",
            "first_release_date": 1431993600,
            "rating": 80.0,
            "rating_count": 1000,
            "cover": {"image_id": "co1234"},
            "genres": [{"id": 1, "name": "RPG"}],
            "platforms": [{"id": 48, "name": "PS4"}],
            "age_ratings": [{"category": 1, "rating": 6}],
        }
        base.update(overrides)
        return base

    def test_basic_fields(self):
        result = build_game_list_item(self._make_raw())
        self.assertEqual(result["id"], 1942)
        self.assertEqual(result["slug"], "the-witcher-3")
        self.assertEqual(result["name"], "The Witcher 3")
        self.assertIsNotNone(result["released"])
        self.assertIn("co1234", result["thumbnail_img_url"])
        self.assertEqual(result["rawg_ratings_count"], 1000)
        self.assertEqual(result["esrb_rating"], "mature")
        self.assertEqual(result["age_rating_min"], 17)

    def test_genres(self):
        result = build_game_list_item(self._make_raw())
        self.assertEqual(len(result["genres"]), 1)
        self.assertEqual(result["genres"][0]["id"], 1)
        self.assertEqual(result["genres"][0]["name"], "RPG")

    def test_platforms(self):
        result = build_game_list_item(self._make_raw())
        self.assertEqual(len(result["platforms"]), 1)
        self.assertEqual(result["platforms"][0]["id"], 48)

    def test_no_genres(self):
        result = build_game_list_item(self._make_raw(genres=None))
        self.assertEqual(result["genres"], [])

    def test_no_platforms(self):
        result = build_game_list_item(self._make_raw(platforms=None))
        self.assertEqual(result["platforms"], [])

    def test_non_dict_genre_skipped(self):
        raw = self._make_raw(genres=["bad", {"id": 1, "name": "RPG"}])
        result = build_game_list_item(raw)
        self.assertEqual(len(result["genres"]), 1)

    def test_no_age_ratings(self):
        result = build_game_list_item(self._make_raw(age_ratings=None))
        self.assertEqual(result["esrb_rating"], "unknown")

    def test_no_rating(self):
        result = build_game_list_item(self._make_raw(rating=None))
        self.assertEqual(result["rawg_rating"], Decimal("0.00"))

    def test_no_rating_count(self):
        result = build_game_list_item(self._make_raw(rating_count=None))
        self.assertEqual(result["rawg_ratings_count"], 0)


class BuildGameDetailTests(TestCase):
    def _make_raw(self, **overrides):
        base = {
            "id": 1942,
            "slug": "the-witcher-3",
            "name": "The Witcher 3",
            "summary": "An RPG game",
            "first_release_date": 1431993600,
            "rating": 80.0,
            "rating_count": 1000,
            "cover": {"image_id": "co1234"},
            "genres": [{"id": 1, "name": "RPG", "slug": "rpg"}],
            "platforms": [{"id": 48, "name": "PS4"}],
            "keywords": [{"id": 10, "name": "open-world"}],
            "age_ratings": [{"category": 1, "rating": 6}],
            "websites": [{"category": 1, "url": "https://thewitcher.com"}],
            "follows": 500,
            "screenshots": [{"image_id": "sc_abc"}],
            "videos": [{"video_id": "yt123", "name": "Trailer"}],
        }
        base.update(overrides)
        return base

    def test_basic_fields(self):
        result = build_game_detail(self._make_raw())
        self.assertEqual(result["id"], 1942)
        self.assertEqual(result["name"], "The Witcher 3")
        self.assertEqual(result["description"], "An RPG game")
        self.assertEqual(result["website"], "https://thewitcher.com")
        self.assertEqual(result["rawg_added"], 500)
        self.assertEqual(result["esrb_rating"], "mature")

    def test_genres_include_slug(self):
        result = build_game_detail(self._make_raw())
        self.assertEqual(result["genres"][0]["slug"], "rpg")

    def test_tags(self):
        result = build_game_detail(self._make_raw())
        self.assertEqual(len(result["tags"]), 1)
        self.assertEqual(result["tags"][0]["id"], 10)

    def test_no_keywords(self):
        result = build_game_detail(self._make_raw(keywords=None))
        self.assertEqual(result["tags"], [])

    def test_screenshots_in_media(self):
        result = build_game_detail(self._make_raw())
        screenshots = [m for m in result["media"] if m["type"] == "screenshot"]
        self.assertEqual(len(screenshots), 1)
        self.assertIn("sc_abc", screenshots[0]["media_url"])
        self.assertIsNone(screenshots[0]["video_url_480"])

    def test_trailers_in_media(self):
        result = build_game_detail(self._make_raw())
        trailers = [m for m in result["media"] if m["type"] == "trailer"]
        self.assertEqual(len(trailers), 1)
        self.assertIn("yt123", trailers[0]["media_url"])
        self.assertIn("yt123", trailers[0]["video_url_480"])
        self.assertIn("yt123", trailers[0]["video_url_max"])

    def test_no_screenshots_no_videos(self):
        result = build_game_detail(self._make_raw(screenshots=None, videos=None))
        self.assertEqual(result["media"], [])

    def test_screenshot_without_image_id_skipped(self):
        result = build_game_detail(self._make_raw(screenshots=[{"no_image_id": True}]))
        screenshots = [m for m in result["media"] if m["type"] == "screenshot"]
        self.assertEqual(len(screenshots), 0)

    def test_video_without_video_id_skipped(self):
        result = build_game_detail(self._make_raw(videos=[{"name": "x"}]))
        trailers = [m for m in result["media"] if m["type"] == "trailer"]
        self.assertEqual(len(trailers), 0)

    def test_stores(self):
        raw = self._make_raw(
            websites=[
                {"category": 1, "url": "https://thewitcher.com"},
                {"url": "https://store.steampowered.com/app/1"},
            ]
        )
        result = build_game_detail(raw)
        self.assertEqual(len(result["stores"]), 1)
        self.assertEqual(result["stores"][0]["name"], "steam")

    def test_tba_status_7(self):
        result = build_game_detail(self._make_raw(status=7))
        self.assertTrue(result["tba"])

    def test_tba_status_8(self):
        result = build_game_detail(self._make_raw(status=8))
        self.assertTrue(result["tba"])

    def test_not_tba_status_0(self):
        result = build_game_detail(self._make_raw(status=0))
        self.assertFalse(result["tba"])

    def test_storyline_fallback(self):
        result = build_game_detail(self._make_raw(summary=None, storyline="A storyline"))
        self.assertEqual(result["description"], "A storyline")

    def test_no_description(self):
        result = build_game_detail(self._make_raw(summary=None))
        self.assertEqual(result["description"], "")


class BuildSimilarGameItemTests(TestCase):
    def _make_raw(self, **overrides):
        base = {
            "id": 100,
            "name": "Similar Game",
            "slug": "similar-game",
            "cover": {"image_id": "co999"},
            "rating": 60.0,
        }
        base.update(overrides)
        return base

    def test_basic(self):
        result = build_similar_game_item(self._make_raw(), 0.85)
        self.assertEqual(result["id"], 100)
        self.assertEqual(result["name"], "Similar Game")
        self.assertEqual(result["slug"], "similar-game")
        self.assertIn("co999", result["thumbnail_img_url"])
        self.assertEqual(result["similarity_score"], 0.85)

    def test_no_cover(self):
        result = build_similar_game_item(self._make_raw(cover=None), 0.5)
        self.assertEqual(result["thumbnail_img_url"], "")

    def test_no_rating(self):
        result = build_similar_game_item(self._make_raw(rating=None), 0.5)
        self.assertEqual(result["rawg_rating"], Decimal("0.00"))
