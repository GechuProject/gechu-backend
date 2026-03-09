from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any, cast

from django.test import TestCase

if TYPE_CHECKING:
    from apps.games.models import Game
from rest_framework.test import APIClient

from apps.games.models import Genre, Platform, Tag
from apps.preferences.models import UserPreference, UserPreferenceGenre, UserPreferencePlatform, UserPreferenceTag
from apps.users.models import User


class PreferenceMeAPITestCase(TestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/preferences/me/"

    def test_preference_me_unauthorized(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_preference_me_empty_when_no_preference(self) -> None:
        user = User.objects.create_user(
            email="test@example.com",
            nickname="tester",
            birth_date=date(1990, 1, 1),
            password="testpass123",
        )
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["genres"], [])
        self.assertEqual(data["platforms"], [])
        self.assertEqual(data["tags"], [])

    def test_preference_me_returns_saved_preferences(self) -> None:
        user = User.objects.create_user(
            email="user2@example.com",
            nickname="user2",
            birth_date=date(1995, 5, 5),
            password="testpass123",
        )
        pref = UserPreference.objects.create(user=user)

        genre1 = Genre.objects.create(rawg_id=1001, name="RPG", slug="rpg")
        genre2 = Genre.objects.create(rawg_id=1002, name="Action", slug="action")
        platform1 = Platform.objects.create(rawg_id=2001, name="PC", slug="pc")
        tag1 = Tag.objects.create(rawg_id=3001, name="Singleplayer", slug="singleplayer")

        UserPreferenceGenre.objects.create(user_preference=pref, genre=genre1)
        UserPreferenceGenre.objects.create(user_preference=pref, genre=genre2)
        UserPreferencePlatform.objects.create(user_preference=pref, platform=platform1)
        UserPreferenceTag.objects.create(user_preference=pref, tag=tag1)

        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        data = cast(dict[str, Any], response.data)
        self.assertEqual(len(data["genres"]), 2)
        genre_ids = {g["id"] for g in data["genres"]}
        self.assertEqual(genre_ids, {genre1.id, genre2.id})
        for g in data["genres"]:
            self.assertIn("name", g)
            self.assertNotIn("slug", g)
        self.assertEqual(len(data["platforms"]), 1)
        self.assertEqual(data["platforms"][0]["id"], platform1.id)
        self.assertEqual(data["platforms"][0]["name"], "PC")
        self.assertNotIn("slug", data["platforms"][0])
        self.assertEqual(len(data["tags"]), 1)
        self.assertEqual(data["tags"][0]["id"], tag1.id)
        self.assertEqual(data["tags"][0]["name"], "Singleplayer")
        self.assertNotIn("slug", data["tags"][0])


class PreferenceMeGenresUpdateAPITestCase(TestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/preferences/me/genres/"

    def test_put_genres_unauthorized(self) -> None:
        response = self.client.put(self.url, {"genre_ids": [1]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_put_genres_invalid_id_returns_400(self) -> None:
        user = User.objects.create_user(
            email="u@ex.com",
            nickname="u",
            birth_date=date(1990, 1, 1),
            password="pw",
        )
        self.client.force_authenticate(user=user)
        response = self.client.put(self.url, {"genre_ids": [99999]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_put_genres_replace_and_return_200(self) -> None:
        user = User.objects.create_user(
            email="u2@ex.com",
            nickname="u2",
            birth_date=date(1995, 1, 1),
            password="pw",
        )
        g1 = Genre.objects.create(rawg_id=101, name="RPG", slug="rpg")
        g2 = Genre.objects.create(rawg_id=102, name="Action", slug="action")
        self.client.force_authenticate(user=user)

        response = self.client.put(self.url, {"genre_ids": [g1.id, g2.id]}, format="json")
        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(len(data["genres"]), 2)
        self.assertEqual({g["id"] for g in data["genres"]}, {g1.id, g2.id})

        response2 = self.client.put(self.url, {"genre_ids": [g1.id]}, format="json")
        self.assertEqual(response2.status_code, 200)
        data2 = cast(dict[str, Any], response2.data)
        self.assertEqual(len(data2["genres"]), 1)
        self.assertEqual(data2["genres"][0]["id"], g1.id)

    def test_put_genres_empty_list_clears(self) -> None:
        user = User.objects.create_user(
            email="u3@ex.com",
            nickname="u3",
            birth_date=date(1992, 1, 1),
            password="pw",
        )
        pref = UserPreference.objects.create(user=user)
        g = Genre.objects.create(rawg_id=103, name="Indie", slug="indie")
        UserPreferenceGenre.objects.create(user_preference=pref, genre=g)
        self.client.force_authenticate(user=user)

        res = self.client.put(self.url, {"genre_ids": []}, format="json")
        self.assertEqual(res.status_code, 200)
        data = cast(dict[str, Any], res.data)
        self.assertEqual(data["genres"], [])


class PreferenceMePlatformsUpdateAPITestCase(TestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/preferences/me/platforms/"

    def test_put_platforms_unauthorized(self) -> None:
        response = self.client.put(self.url, {"platform_ids": [1]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_put_platforms_invalid_id_returns_400(self) -> None:
        user = User.objects.create_user(
            email="u@ex.com",
            nickname="u",
            birth_date=date(1990, 1, 1),
            password="pw",
        )
        self.client.force_authenticate(user=user)
        response = self.client.put(self.url, {"platform_ids": [99999]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_put_platforms_replace_and_return_200(self) -> None:
        user = User.objects.create_user(
            email="u2@ex.com",
            nickname="u2",
            birth_date=date(1995, 1, 1),
            password="pw",
        )
        p1 = Platform.objects.create(rawg_id=201, name="PC", slug="pc")
        p2 = Platform.objects.create(rawg_id=202, name="PlayStation", slug="playstation")
        self.client.force_authenticate(user=user)

        response = self.client.put(self.url, {"platform_ids": [p1.id, p2.id]}, format="json")
        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(len(data["platforms"]), 2)
        self.assertEqual({p["id"] for p in data["platforms"]}, {p1.id, p2.id})

        response2 = self.client.put(self.url, {"platform_ids": [p1.id]}, format="json")
        self.assertEqual(response2.status_code, 200)
        data2 = cast(dict[str, Any], response2.data)
        self.assertEqual(len(data2["platforms"]), 1)
        self.assertEqual(data2["platforms"][0]["id"], p1.id)

    def test_put_platforms_empty_list_clears(self) -> None:
        user = User.objects.create_user(
            email="u3@ex.com",
            nickname="u3",
            birth_date=date(1992, 1, 1),
            password="pw",
        )
        pref = UserPreference.objects.create(user=user)
        p = Platform.objects.create(rawg_id=203, name="Xbox", slug="xbox")
        UserPreferencePlatform.objects.create(user_preference=pref, platform=p)
        self.client.force_authenticate(user=user)

        res = self.client.put(self.url, {"platform_ids": []}, format="json")
        self.assertEqual(res.status_code, 200)
        data = cast(dict[str, Any], res.data)
        self.assertEqual(data["platforms"], [])


class PreferenceMeTagsUpdateAPITestCase(TestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/preferences/me/tags/"

    def test_put_tags_unauthorized(self) -> None:
        response = self.client.put(self.url, {"tag_ids": [1]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_put_tags_invalid_id_returns_400(self) -> None:
        user = User.objects.create_user(
            email="u@ex.com",
            nickname="u",
            birth_date=date(1990, 1, 1),
            password="pw",
        )
        self.client.force_authenticate(user=user)
        response = self.client.put(self.url, {"tag_ids": [99999]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_put_tags_replace_and_return_200(self) -> None:
        user = User.objects.create_user(
            email="u2@ex.com",
            nickname="u2",
            birth_date=date(1995, 1, 1),
            password="pw",
        )
        t1 = Tag.objects.create(rawg_id=301, name="RPG", slug="rpg")
        t2 = Tag.objects.create(rawg_id=302, name="Multiplayer", slug="multiplayer")
        self.client.force_authenticate(user=user)

        response = self.client.put(self.url, {"tag_ids": [t1.id, t2.id]}, format="json")
        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(len(data["tags"]), 2)
        self.assertEqual({t["id"] for t in data["tags"]}, {t1.id, t2.id})

        response2 = self.client.put(self.url, {"tag_ids": [t1.id]}, format="json")
        self.assertEqual(response2.status_code, 200)
        data2 = cast(dict[str, Any], response2.data)
        self.assertEqual(len(data2["tags"]), 1)
        self.assertEqual(data2["tags"][0]["id"], t1.id)

    def test_put_tags_empty_list_clears(self) -> None:
        user = User.objects.create_user(
            email="u3@ex.com",
            nickname="u3",
            birth_date=date(1992, 1, 1),
            password="pw",
        )
        pref = UserPreference.objects.create(user=user)
        t = Tag.objects.create(rawg_id=303, name="Singleplayer", slug="singleplayer")
        UserPreferenceTag.objects.create(user_preference=pref, tag=t)
        self.client.force_authenticate(user=user)

        res = self.client.put(self.url, {"tag_ids": []}, format="json")
        self.assertEqual(res.status_code, 200)
        data = cast(dict[str, Any], res.data)
        self.assertEqual(data["tags"], [])


def _create_game(**kwargs: Any) -> Game:
    from apps.games.models import Game

    defaults = {
        "rawg_id": 5001,
        "slug": "test-game",
        "name": "Test Game",
        "thumbnail_img_url": "https://example.com/thumb.jpg",
        "website": "https://example.com",
        "is_visible": True,
    }
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


class PreferenceGameReactionUpdateAPITestCase(TestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()

    def _url(self, game_id: int) -> str:
        return f"/api/v1/preferences/games/{game_id}/"

    def test_put_game_reaction_unauthorized(self) -> None:
        game = _create_game()
        response = self.client.put(self._url(game.id), {"is_saved": True}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_put_game_reaction_game_not_found(self) -> None:
        user = User.objects.create_user(
            email="u@ex.com",
            nickname="u",
            birth_date=date(1990, 1, 1),
            password="pw",
        )
        self.client.force_authenticate(user=user)
        response = self.client.put(self._url(99999), {"is_saved": True}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_put_game_reaction_empty_body_returns_400(self) -> None:
        user = User.objects.create_user(
            email="u@ex.com",
            nickname="u",
            birth_date=date(1990, 1, 1),
            password="pw",
        )
        game = _create_game()
        self.client.force_authenticate(user=user)
        response = self.client.put(self._url(game.id), {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_put_game_reaction_invalid_reaction_returns_400(self) -> None:
        user = User.objects.create_user(
            email="u@ex.com",
            nickname="u",
            birth_date=date(1990, 1, 1),
            password="pw",
        )
        game = _create_game()
        self.client.force_authenticate(user=user)
        response = self.client.put(
            self._url(game.id),
            {"reaction": "invalid_value"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "INVALID_REACTION")
        self.assertEqual(
            data.get("message"),
            "reaction은 like, dislike, neutral 중 하나여야 합니다.",
        )

    def test_put_game_reaction_is_saved(self) -> None:
        user = User.objects.create_user(
            email="u@ex.com",
            nickname="u",
            birth_date=date(1990, 1, 1),
            password="pw",
        )
        game = _create_game()
        self.client.force_authenticate(user=user)

        response = self.client.put(self._url(game.id), {"is_saved": True}, format="json")
        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["game_id"], game.id)
        self.assertTrue(data["is_saved"])
        self.assertEqual(data["reaction"], "neutral")
        self.assertIn("updated_at", data)

        response2 = self.client.put(self._url(game.id), {"is_saved": False}, format="json")
        self.assertEqual(response2.status_code, 200)
        data2 = cast(dict[str, Any], response2.data)
        self.assertFalse(data2["is_saved"])

    def test_put_game_reaction_like_dislike(self) -> None:
        user = User.objects.create_user(
            email="u2@ex.com",
            nickname="u2",
            birth_date=date(1995, 1, 1),
            password="pw",
        )
        game = _create_game()
        self.client.force_authenticate(user=user)

        response = self.client.put(self._url(game.id), {"reaction": "like"}, format="json")
        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["reaction"], "like")

        response2 = self.client.put(self._url(game.id), {"reaction": "dislike"}, format="json")
        self.assertEqual(response2.status_code, 200)
        data2 = cast(dict[str, Any], response2.data)
        self.assertEqual(data2["reaction"], "dislike")

        response3 = self.client.put(self._url(game.id), {"reaction": "neutral"}, format="json")
        self.assertEqual(response3.status_code, 200)
        data3 = cast(dict[str, Any], response3.data)
        self.assertEqual(data3["reaction"], "neutral")

    def test_put_game_reaction_both_is_saved_and_reaction(self) -> None:
        user = User.objects.create_user(
            email="u3@ex.com",
            nickname="u3",
            birth_date=date(1992, 1, 1),
            password="pw",
        )
        game = _create_game()
        self.client.force_authenticate(user=user)

        response = self.client.put(
            self._url(game.id),
            {"is_saved": True, "reaction": "like"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertTrue(data["is_saved"])
        self.assertEqual(data["reaction"], "like")
