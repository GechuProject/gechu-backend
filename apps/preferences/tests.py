from datetime import date
from typing import Any, cast

from django.test import TestCase
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
            self.assertIn("slug", g)
        self.assertEqual(len(data["platforms"]), 1)
        self.assertEqual(data["platforms"][0]["id"], platform1.id)
        self.assertEqual(data["platforms"][0]["name"], "PC")
        self.assertEqual(data["platforms"][0]["slug"], "pc")
        self.assertEqual(len(data["tags"]), 1)
        self.assertEqual(data["tags"][0]["id"], tag1.id)
        self.assertEqual(data["tags"][0]["name"], "Singleplayer")
        self.assertEqual(data["tags"][0]["slug"], "singleplayer")
