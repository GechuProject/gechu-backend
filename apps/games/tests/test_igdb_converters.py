from datetime import date
from decimal import Decimal
from typing import Any

from django.test import SimpleTestCase

from apps.games.igdb.converters import (
    _parse_cover_url,
    _parse_esrb,
    _parse_rating,
    _parse_website,
    _timestamp_to_date,
    convert_game,
    convert_genre,
    convert_platform,
    convert_screenshot,
    convert_tag,
    convert_trailer,
    extract_genre_igdb_ids,
    extract_keyword_igdb_ids,
    extract_platform_entries,
    extract_store_entries,
)


class TimestampToDateTests(SimpleTestCase):
    def test_valid_timestamp(self) -> None:
        # 2020-01-01 00:00:00 UTC
        self.assertEqual(_timestamp_to_date(1577836800), date(2020, 1, 1))

    def test_none_returns_none(self) -> None:
        self.assertIsNone(_timestamp_to_date(None))

    def test_zero_returns_none(self) -> None:
        self.assertIsNone(_timestamp_to_date(0))

    def test_overflow_returns_none(self) -> None:
        self.assertIsNone(_timestamp_to_date(99999999999999))


class ParseEsrbTests(SimpleTestCase):
    def test_none_returns_unknown(self) -> None:
        self.assertEqual(_parse_esrb(None), ("unknown", 0))

    def test_empty_list_returns_unknown(self) -> None:
        self.assertEqual(_parse_esrb([]), ("unknown", 0))

    def test_esrb_mature(self) -> None:
        ratings = [{"organization": 1, "rating_category": 6}]
        self.assertEqual(_parse_esrb(ratings), ("mature", 17))

    def test_esrb_teen(self) -> None:
        ratings = [{"organization": 1, "rating_category": 5}]
        self.assertEqual(_parse_esrb(ratings), ("teen", 13))

    def test_esrb_everyone(self) -> None:
        ratings = [{"organization": 1, "rating_category": 3}]
        self.assertEqual(_parse_esrb(ratings), ("everyone", 0))

    def test_esrb_everyone_10_plus(self) -> None:
        ratings = [{"organization": 1, "rating_category": 4}]
        self.assertEqual(_parse_esrb(ratings), ("everyone_10_plus", 10))

    def test_esrb_adults_only(self) -> None:
        ratings = [{"organization": 1, "rating_category": 7}]
        self.assertEqual(_parse_esrb(ratings), ("adults_only", 18))

    def test_esrb_rating_pending(self) -> None:
        ratings = [{"organization": 1, "rating_category": 1}]
        self.assertEqual(_parse_esrb(ratings), ("rating_pending", 0))

    def test_esrb_early_childhood(self) -> None:
        ratings = [{"organization": 1, "rating_category": 2}]
        self.assertEqual(_parse_esrb(ratings), ("everyone", 0))

    def test_pegi_only_returns_unknown(self) -> None:
        ratings = [{"organization": 2, "rating_category": 3}]
        self.assertEqual(_parse_esrb(ratings), ("unknown", 0))

    def test_non_dict_entries_skipped(self) -> None:
        ratings: list[Any] = ["not_a_dict", {"organization": 1, "rating_category": 6}]
        self.assertEqual(_parse_esrb(ratings), ("mature", 17))

    def test_unknown_rating_id(self) -> None:
        ratings = [{"organization": 1, "rating_category": 999}]
        self.assertEqual(_parse_esrb(ratings), ("unknown", 0))

    def test_mixed_categories_picks_esrb(self) -> None:
        ratings = [
            {"organization": 2, "rating_category": 5},
            {"organization": 1, "rating_category": 5},
        ]
        self.assertEqual(_parse_esrb(ratings), ("teen", 13))


class ParseRatingTests(SimpleTestCase):
    def test_none_returns_zero(self) -> None:
        self.assertEqual(_parse_rating(None), Decimal("0.00"))

    def test_zero_returns_zero(self) -> None:
        self.assertEqual(_parse_rating(0), Decimal("0.00"))

    def test_normal_rating(self) -> None:
        self.assertEqual(_parse_rating(80), Decimal("4"))

    def test_max_rating(self) -> None:
        self.assertEqual(_parse_rating(100), Decimal("5"))

    def test_over_100_capped_at_5(self) -> None:
        self.assertEqual(_parse_rating(120), Decimal("5.00"))

    def test_float_rating(self) -> None:
        result = _parse_rating(75.5)
        self.assertEqual(result, Decimal("75.5") / Decimal("20"))


class ParseCoverUrlTests(SimpleTestCase):
    def test_valid_cover(self) -> None:
        cover = {"image_id": "co1234"}
        result = _parse_cover_url(cover)
        self.assertIn("co1234", result)
        self.assertIn("cover_big", result)

    def test_none_returns_empty(self) -> None:
        self.assertEqual(_parse_cover_url(None), "")

    def test_non_dict_returns_empty(self) -> None:
        self.assertEqual(_parse_cover_url("not_a_dict"), "")  # type: ignore[arg-type]

    def test_missing_image_id_returns_empty(self) -> None:
        self.assertEqual(_parse_cover_url({}), "")

    def test_empty_image_id_returns_empty(self) -> None:
        self.assertEqual(_parse_cover_url({"image_id": ""}), "")


class ParseWebsiteTests(SimpleTestCase):
    def test_official_website(self) -> None:
        websites = [{"category": 1, "url": "https://example.com"}]
        self.assertEqual(_parse_website(websites), "https://example.com")

    def test_none_returns_empty(self) -> None:
        self.assertEqual(_parse_website(None), "")

    def test_empty_list_returns_empty(self) -> None:
        self.assertEqual(_parse_website([]), "")

    def test_no_official_website(self) -> None:
        websites = [{"category": 2, "url": "https://twitter.com/game"}]
        self.assertEqual(_parse_website(websites), "")

    def test_non_dict_entries_skipped(self) -> None:
        websites: list[Any] = ["not_a_dict", {"category": 1, "url": "https://example.com"}]
        self.assertEqual(_parse_website(websites), "https://example.com")

    def test_missing_url_returns_empty_string(self) -> None:
        websites = [{"category": 1}]
        self.assertEqual(_parse_website(websites), "")


class ConvertGenreTests(SimpleTestCase):
    def test_basic(self) -> None:
        raw = {"id": 5, "name": "Shooter", "slug": "shooter"}
        result = convert_genre(raw)
        self.assertEqual(result["rawg_id"], 5)
        self.assertEqual(result["name"], "Shooter")
        self.assertEqual(result["slug"], "shooter")

    def test_missing_name_slug(self) -> None:
        raw = {"id": 1}
        result = convert_genre(raw)
        self.assertEqual(result["name"], "")
        self.assertEqual(result["slug"], "")

    def test_long_name_truncated(self) -> None:
        raw = {"id": 1, "name": "x" * 100, "slug": "y" * 100}
        result = convert_genre(raw)
        self.assertEqual(len(result["name"]), 50)
        self.assertEqual(len(result["slug"]), 50)


class ConvertPlatformTests(SimpleTestCase):
    def test_basic(self) -> None:
        raw = {"id": 48, "name": "PlayStation 4", "slug": "ps4"}
        result = convert_platform(raw)
        self.assertEqual(result["rawg_id"], 48)
        self.assertEqual(result["name"], "PlayStation 4")
        self.assertIsNone(result["icon_url"])

    def test_with_logo(self) -> None:
        raw = {
            "id": 48,
            "name": "PS4",
            "slug": "ps4",
            "platform_logo": {"image_id": "pl_abc"},
        }
        result = convert_platform(raw)
        self.assertIn("pl_abc", result["icon_url"])
        self.assertIn("thumb", result["icon_url"])

    def test_no_logo(self) -> None:
        raw = {"id": 48, "name": "PS4", "slug": "ps4", "platform_logo": None}
        result = convert_platform(raw)
        self.assertIsNone(result["icon_url"])

    def test_logo_non_dict(self) -> None:
        raw = {"id": 48, "name": "PS4", "slug": "ps4", "platform_logo": 123}
        result = convert_platform(raw)
        self.assertIsNone(result["icon_url"])


class ConvertTagTests(SimpleTestCase):
    def test_basic(self) -> None:
        raw = {"id": 10, "name": "Action", "slug": "action"}
        result = convert_tag(raw)
        self.assertEqual(result["rawg_id"], 10)
        self.assertEqual(result["name"], "Action")
        self.assertEqual(result["slug"], "action")


class ConvertGameTests(SimpleTestCase):
    def _make_raw(self, **overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": 1942,
            "slug": "the-witcher-3",
            "name": "The Witcher 3",
            "summary": "An RPG game",
            "first_release_date": 1431993600,  # 2015-05-19
            "rating": 80.0,
            "rating_count": 1000,
            "cover": {"image_id": "co1234"},
            "websites": [{"category": 1, "url": "https://thewitcher.com"}],
            "age_ratings": [{"organization": 1, "rating_category": 6}],
            "follows": 500,
            "updated_at": 1609459200,  # 2021-01-01
        }
        base.update(overrides)
        return base

    def test_basic_conversion(self) -> None:
        raw = self._make_raw()
        result = convert_game(raw)
        self.assertEqual(result["rawg_id"], 1942)
        self.assertEqual(result["slug"], "the-witcher-3")
        self.assertEqual(result["name"], "The Witcher 3")
        self.assertEqual(result["description"], "An RPG game")
        self.assertEqual(result["released"], date(2015, 5, 19))
        self.assertIn("co1234", result["thumbnail_img_url"])
        self.assertEqual(result["website"], "https://thewitcher.com")
        self.assertEqual(result["rawg_rating"], Decimal("80") / Decimal("20"))
        self.assertEqual(result["rawg_ratings_count"], 1000)
        self.assertEqual(result["esrb_rating"], "mature")
        self.assertEqual(result["age_rating_min"], 17)
        self.assertEqual(result["rawg_added"], 500)
        self.assertFalse(result["tba"])
        self.assertIsNone(result["metacritic"])
        self.assertEqual(result["playtime"], 0)
        self.assertIsNotNone(result["synced_at"])

    def test_missing_slug_fallback(self) -> None:
        raw = self._make_raw(slug=None)
        result = convert_game(raw)
        self.assertEqual(result["slug"], "igdb-1942")

    def test_storyline_fallback(self) -> None:
        raw = self._make_raw(summary=None, storyline="A storyline")
        result = convert_game(raw)
        self.assertEqual(result["description"], "A storyline")

    def test_no_description(self) -> None:
        raw = self._make_raw(summary=None)
        result = convert_game(raw)
        self.assertIsNone(result["description"])

    def test_no_cover(self) -> None:
        raw = self._make_raw(cover=None)
        result = convert_game(raw)
        self.assertEqual(result["thumbnail_img_url"], "")

    def test_no_updated_at(self) -> None:
        raw = self._make_raw(updated_at=None)
        result = convert_game(raw)
        self.assertIsNone(result["rawg_updated"])


class ExtractGenreIgdbIdsTests(SimpleTestCase):
    def test_basic(self) -> None:
        raw = {"genres": [{"id": 1}, {"id": 2}]}
        self.assertEqual(extract_genre_igdb_ids(raw), [1, 2])

    def test_empty(self) -> None:
        self.assertEqual(extract_genre_igdb_ids({}), [])

    def test_none(self) -> None:
        self.assertEqual(extract_genre_igdb_ids({"genres": None}), [])

    def test_non_dict_entries_skipped(self) -> None:
        raw: dict[str, Any] = {"genres": [{"id": 1}, "bad", {"id": None}]}
        self.assertEqual(extract_genre_igdb_ids(raw), [1])


class ExtractKeywordIgdbIdsTests(SimpleTestCase):
    def test_basic(self) -> None:
        raw = {"keywords": [{"id": 10}, {"id": 20}]}
        self.assertEqual(extract_keyword_igdb_ids(raw), [10, 20])

    def test_empty(self) -> None:
        self.assertEqual(extract_keyword_igdb_ids({}), [])

    def test_non_dict_entries_skipped(self) -> None:
        raw: dict[str, Any] = {"keywords": [{"id": 10}, "bad"]}
        self.assertEqual(extract_keyword_igdb_ids(raw), [10])


class ExtractPlatformEntriesTests(SimpleTestCase):
    def test_basic(self) -> None:
        raw = {"platforms": [{"id": 48}, {"id": 49}]}
        entries = extract_platform_entries(raw)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["platform_rawg_id"], 48)
        self.assertEqual(entries[0]["requirements_minimum"], "")

    def test_empty(self) -> None:
        self.assertEqual(extract_platform_entries({}), [])

    def test_non_dict_entries_skipped(self) -> None:
        raw: dict[str, Any] = {"platforms": [{"id": 48}, "bad", {"no_id": True}]}
        self.assertEqual(len(extract_platform_entries(raw)), 1)


class ExtractStoreEntriesTests(SimpleTestCase):
    def test_steam_url(self) -> None:
        raw = {"websites": [{"url": "https://store.steampowered.com/app/1234"}]}
        entries = extract_store_entries(raw)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["store_slug"], "steam")

    def test_epic_url(self) -> None:
        raw = {"websites": [{"url": "https://www.epicgames.com/store/p/game"}]}
        entries = extract_store_entries(raw)
        self.assertEqual(entries[0]["store_slug"], "epic-games")

    def test_gog_url(self) -> None:
        raw = {"websites": [{"url": "https://www.gog.com/game/title"}]}
        entries = extract_store_entries(raw)
        self.assertEqual(entries[0]["store_slug"], "gog")

    def test_non_store_url_skipped(self) -> None:
        raw = {"websites": [{"url": "https://twitter.com/game"}]}
        self.assertEqual(extract_store_entries(raw), [])

    def test_empty_url_skipped(self) -> None:
        raw = {"websites": [{"url": ""}]}
        self.assertEqual(extract_store_entries(raw), [])

    def test_non_dict_skipped(self) -> None:
        raw: dict[str, Any] = {"websites": ["bad"]}
        self.assertEqual(extract_store_entries(raw), [])

    def test_no_websites(self) -> None:
        self.assertEqual(extract_store_entries({}), [])

    def test_multiple_stores(self) -> None:
        raw = {
            "websites": [
                {"url": "https://store.steampowered.com/app/1"},
                {"url": "https://www.gog.com/game/t"},
                {"url": "https://twitter.com/x"},
            ]
        }
        entries = extract_store_entries(raw)
        self.assertEqual(len(entries), 2)
        slugs = {e["store_slug"] for e in entries}
        self.assertEqual(slugs, {"steam", "gog"})


class ConvertScreenshotTests(SimpleTestCase):
    def test_basic(self) -> None:
        raw = {"id": 100, "image_id": "sc_abc"}
        result = convert_screenshot(1942, raw)
        self.assertEqual(result["game_id"], 1942)
        self.assertEqual(result["rawg_id"], 100)
        self.assertEqual(result["type"], "screenshot")
        self.assertIn("sc_abc", result["media_url"])
        self.assertIn("screenshot_big", result["media_url"])
        self.assertIsNone(result["video_url_480"])
        self.assertIsNone(result["video_url_max"])

    def test_missing_image_id(self) -> None:
        raw = {"id": 100, "image_id": ""}
        result = convert_screenshot(1942, raw)
        self.assertEqual(result["media_url"], "")


class ConvertTrailerTests(SimpleTestCase):
    def test_basic(self) -> None:
        raw = {"id": 200, "video_id": "abc123", "name": "Trailer 1"}
        result = convert_trailer(1942, raw)
        self.assertEqual(result["game_id"], 1942)
        self.assertEqual(result["rawg_id"], 200)
        self.assertEqual(result["type"], "trailer")
        self.assertIn("abc123", result["media_url"])
        self.assertEqual(result["video_url_480"], "https://www.youtube.com/embed/abc123")
        self.assertEqual(result["video_url_max"], "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(result["video_name"], "Trailer 1")

    def test_missing_video_id(self) -> None:
        raw = {"id": 200, "video_id": ""}
        result = convert_trailer(1942, raw)
        self.assertEqual(result["media_url"], "")
        self.assertIsNone(result["video_url_480"])
        self.assertIsNone(result["video_url_max"])

    def test_missing_name(self) -> None:
        raw = {"id": 200, "video_id": "abc123"}
        result = convert_trailer(1942, raw)
        self.assertIsNone(result["video_name"])
