from __future__ import annotations

import itertools
from datetime import date
from typing import Any, cast
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.games.models import Genre, Platform, Tag
from apps.preferences.models import UserPreference
from apps.users.models import User

_counter = itertools.count(1)

# IGDB game IDs used in tests (no DB Game model)
IGDB_GAME_ID_BASE = 9000


class PreferenceBaseTestCase(TestCase):
    """공통 유저 생성 및 인증을 담당하는 베이스 클래스"""

    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.client.raise_request_exception = True
        self.user = User.objects.create_user(
            email=f"test_{self.__class__.__name__}@example.com",
            nickname="tester",
            birth_date=date(1990, 1, 1),
            password="testpass123",
        )
        UserPreference.objects.get_or_create(user=self.user)
        # 기본적으로 인증된 상태로 시작
        self.client.force_authenticate(user=self.user)

    def _next_igdb_game_id(self) -> int:
        return IGDB_GAME_ID_BASE + next(_counter)

    def _create_genre(self, **kwargs: Any) -> Genre:
        uid = next(_counter)
        return Genre.objects.create(igdb_id=uid, name=f"Genre-{uid}", slug=f"genre-{uid}", **kwargs)

    def _create_platform(self, **kwargs: Any) -> Platform:
        uid = next(_counter)
        return Platform.objects.create(igdb_id=uid, name=f"Platform-{uid}", slug=f"platform-{uid}", **kwargs)

    def _create_tag(self, **kwargs: Any) -> Tag:
        uid = next(_counter)
        return Tag.objects.create(igdb_id=uid, name=f"Tag-{uid}", slug=f"tag-{uid}", **kwargs)


class PreferenceMeAPITestCase(PreferenceBaseTestCase):
    """내 선호 정보 조회 및 수정 테스트 (GET/PUT)"""

    url = "/api/v1/preferences/me/"

    def test_preference_me_unauthorized(self) -> None:
        self.client.force_authenticate(user=None)  # 인증 해제 후 테스트
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_get_preference_me_success(self) -> None:
        # 데이터가 없을 때의 초기 응답 확인
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, f"Detail: {response.data}")

        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["genres"], [])
        self.assertEqual(data["platforms"], [])
        self.assertEqual(data["tags"], [])

    def test_put_preferences_replace_all(self) -> None:
        g = self._create_genre()
        p = self._create_platform()
        t = self._create_tag()

        payload: dict[str, list[int]] = {"genre_ids": [g.id], "platform_ids": [p.id], "tag_ids": [t.id]}
        response = self.client.put(self.url, payload, format="json")
        self.assertEqual(response.status_code, 200, f"Detail: {response.data}")

        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["genres"][0]["id"], g.id)
        self.assertEqual(data["platforms"][0]["id"], p.id)

    def test_put_preferences_empty_list_clears_all(self) -> None:
        # 빈 배열 전송 시 초기화 테스트
        payload: dict[str, list[int]] = {"genre_ids": [], "platform_ids": [], "tag_ids": []}
        response = self.client.put(self.url, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["genres"], [])
        self.assertEqual(response.data["platforms"], [])
        self.assertEqual(response.data["tags"], [])


class PreferenceGameReactionAPITestCase(PreferenceBaseTestCase):
    """게임 반응 수정 테스트 (PATCH)"""

    def _url(self, game_id: int) -> str:
        return f"/api/v1/preferences/games/{game_id}/"

    def test_patch_game_reaction_success(self) -> None:
        igdb_game_id = self._next_igdb_game_id()
        payload = {"reaction": "like", "is_saved": True, "interaction_source": "detail_page"}

        response = self.client.patch(self._url(igdb_game_id), payload, format="json")
        self.assertEqual(response.status_code, 200, f"Detail: {response.data}")

        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["reaction"], "like")
        self.assertTrue(data["is_saved"])

    def test_patch_game_reaction_invalid_value(self) -> None:
        igdb_game_id = self._next_igdb_game_id()
        response = self.client.patch(self._url(igdb_game_id), {"reaction": "wrong"}, format="json")
        self.assertEqual(response.status_code, 400)


class SavedGamesAPITestCase(PreferenceBaseTestCase):
    """찜한 게임 목록 테스트 (GET)"""

    url = "/api/v1/preferences/me/saved-games/"

    def test_saved_games_unauthorized(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    @patch("apps.preferences.views.igdb_cache.get_games_by_ids")
    def test_get_saved_games_empty(self, mock_get_games: object) -> None:
        mock_get_games.return_value = []  # type: ignore[attr-defined]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, f"Detail: {response.data}")
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])

    @patch("apps.preferences.views.igdb_cache.get_games_by_ids")
    def test_get_saved_games_success(self, mock_get_games: object) -> None:
        igdb_game_id = self._next_igdb_game_id()
        # 게임을 찜하기
        self.client.patch(
            f"/api/v1/preferences/games/{igdb_game_id}/",
            {"is_saved": True, "interaction_source": "detail_page"},
            format="json",
        )

        mock_get_games.return_value = [  # type: ignore[attr-defined]
            {
                "id": igdb_game_id,
                "name": "Saved Game",
                "slug": "saved-game",
                "thumbnail_img_url": "https://example.com/thumb.jpg",
                "rawg_rating": 4.5,
            }
        ]

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, f"Detail: {response.data}")

        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], igdb_game_id)

    @patch("apps.preferences.views.igdb_cache.get_games_by_ids")
    def test_get_saved_games_excludes_unsaved(self, mock_get_games: object) -> None:
        igdb_game_id = self._next_igdb_game_id()
        self.client.patch(
            f"/api/v1/preferences/games/{igdb_game_id}/",
            {"is_saved": False, "interaction_source": "detail_page"},
            format="json",
        )

        mock_get_games.return_value = []  # type: ignore[attr-defined]

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)


class GameAffinitiesAPITestCase(PreferenceBaseTestCase):
    """게임 취향 상태 목록 테스트 (GET)"""

    url = "/api/v1/preferences/me/game-affinities/"

    def test_game_affinities_unauthorized(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    @patch("apps.preferences.views.igdb_cache.get_games_by_ids")
    def test_get_game_affinities_empty(self, mock_get_games: object) -> None:
        mock_get_games.return_value = []  # type: ignore[attr-defined]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, f"Detail: {response.data}")
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])

    @patch("apps.preferences.views.igdb_cache.get_games_by_ids")
    def test_get_game_affinities_success(self, mock_get_games: object) -> None:
        igdb_game_id = self._next_igdb_game_id()
        self.client.patch(
            f"/api/v1/preferences/games/{igdb_game_id}/",
            {"reaction": "like", "interaction_source": "detail_page"},
            format="json",
        )

        mock_get_games.return_value = [  # type: ignore[attr-defined]
            {
                "id": igdb_game_id,
                "name": "Liked Game",
                "slug": "liked-game",
                "thumbnail_img_url": "https://example.com/thumb.jpg",
                "rawg_rating": 4.5,
            }
        ]

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200, f"Detail: {response.data}")

        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["count"], 1)
        result = data["results"][0]
        self.assertEqual(result["id"], igdb_game_id)
        self.assertEqual(result["like_state"], 1)
