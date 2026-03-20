from typing import Any
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.games.igdb.client import IgdbClient, get_igdb_client, get_image_url
from apps.games.igdb.exceptions import (
    IgdbAuthError,
    IgdbNotFoundError,
    IgdbRateLimitError,
    IgdbServerError,
)


class GetImageUrlTests(TestCase):
    def test_default_size(self) -> None:
        url = get_image_url("co1234")
        self.assertEqual(url, "https://images.igdb.com/igdb/image/upload/t_cover_big/co1234.jpg")

    def test_custom_size(self) -> None:
        url = get_image_url("sc_abc", "screenshot_big")
        self.assertEqual(url, "https://images.igdb.com/igdb/image/upload/t_screenshot_big/sc_abc.jpg")


@override_settings(IGDB_CLIENT_ID="test_id", IGDB_CLIENT_SECRET="test_secret")
class IgdbClientTests(TestCase):
    def _make_client(self, mock_session: Any) -> tuple[IgdbClient, MagicMock]:
        """Create an IgdbClient with mocked session and token fetch."""
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "test_token"}
        mock_session.return_value = token_resp
        # Patch _build_session so the real session is mocked
        with patch("apps.games.igdb.client._build_session") as mock_build:
            session = MagicMock()
            # Token fetch response
            session.post.return_value = token_resp
            mock_build.return_value = session
            client = IgdbClient()
        return client, session

    @patch("apps.games.igdb.client._build_session")
    def test_init_fetches_token(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok123"}
        session.post.return_value = token_resp
        mock_build.return_value = session
        client = IgdbClient()
        self.assertEqual(client._access_token, "tok123")

    @patch("apps.games.igdb.client._build_session")
    def test_post_success(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        # First call: token fetch
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        # Second call: actual API call
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = [{"id": 1}]
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        result = client._post("games", "fields id;")
        self.assertEqual(result, [{"id": 1}])

    @patch("apps.games.igdb.client._build_session")
    def test_post_401_raises_auth_error(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 401
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        with self.assertRaises(IgdbAuthError):
            client._post("games", "fields id;")

    @patch("apps.games.igdb.client._build_session")
    def test_post_429_raises_rate_limit(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 429
        api_resp.headers = {"Retry-After": "5"}
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        with self.assertRaises(IgdbRateLimitError) as ctx:
            client._post("games", "fields id;")
        self.assertEqual(ctx.exception.retry_after, 5)

    @patch("apps.games.igdb.client._build_session")
    def test_post_404_raises_not_found(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 404
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        with self.assertRaises(IgdbNotFoundError):
            client._post("games", "fields id;")

    @patch("apps.games.igdb.client._build_session")
    def test_post_500_raises_server_error(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 500
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        with self.assertRaises(IgdbServerError):
            client._post("games", "fields id;")

    @patch("apps.games.igdb.client._build_session")
    def test_post_with_auth_retry(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        # First API call: 401, then re-fetch token, then success
        api_401 = MagicMock()
        api_401.status_code = 401
        token_resp2 = MagicMock()
        token_resp2.raise_for_status.return_value = None
        token_resp2.json.return_value = {"access_token": "tok2"}
        api_ok = MagicMock()
        api_ok.status_code = 200
        api_ok.raise_for_status.return_value = None
        api_ok.json.return_value = [{"id": 1}]
        session.post.side_effect = [token_resp, api_401, token_resp2, api_ok]
        mock_build.return_value = session
        client = IgdbClient()
        with self.assertLogs("apps.games.igdb.client", level="WARNING"):
            result = client._post_with_auth_retry("games", "fields id;")
        self.assertEqual(result, [{"id": 1}])

    @patch("apps.games.igdb.client._build_session")
    def test_get_game_success(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = [{"id": 42, "name": "Game"}]
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        result = client.get_game(42)
        self.assertEqual(result["id"], 42)

    @patch("apps.games.igdb.client._build_session")
    def test_get_game_not_found(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = []
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        with self.assertRaises(IgdbNotFoundError):
            client.get_game(9999)

    @patch("apps.games.igdb.client._build_session")
    def test_search_games_with_query(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = [{"id": 1}]
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        result = client.search_games(query="witcher")
        self.assertEqual(result, [{"id": 1}])

    @patch("apps.games.igdb.client._build_session")
    def test_search_games_with_filters(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = [{"id": 2}]
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        result = client.search_games(
            genre_ids=[1],
            platform_ids=[48],
            tag_ids=[10],
            theme_ids=[5],
            game_mode_ids=[2],
        )
        self.assertEqual(result, [{"id": 2}])
        # Check the query string contains filter clauses
        call_args = session.post.call_args_list[-1]
        query_data = call_args.kwargs.get("data") or call_args[1].get("data", "")
        self.assertIn("genres", query_data)
        self.assertIn("platforms", query_data)

    @patch("apps.games.igdb.client._build_session")
    def test_get_games_by_ids_empty(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        mock_build.return_value = session
        client = IgdbClient()
        self.assertEqual(client.get_games_by_ids([]), [])

    @patch("apps.games.igdb.client._build_session")
    def test_get_games_by_ids_success(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = [{"id": 1}, {"id": 2}]
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        result = client.get_games_by_ids([1, 2])
        self.assertEqual(len(result), 2)

    @patch("apps.games.igdb.client._build_session")
    def test_iter_genres(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = [{"id": 1, "name": "Action"}]
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        pages = list(client.iter_genres())
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0][0]["name"], "Action")

    @patch("apps.games.igdb.client._build_session")
    def test_iter_platforms(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = [{"id": 48, "name": "PS4"}]
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        pages = list(client.iter_platforms())
        self.assertEqual(len(pages), 1)

    @patch("apps.games.igdb.client._build_session")
    def test_iter_keywords(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = [{"id": 10, "name": "stealth"}]
        session.post.side_effect = [token_resp, api_resp]
        mock_build.return_value = session
        client = IgdbClient()
        pages = list(client.iter_keywords())
        self.assertEqual(len(pages), 1)

    @patch("apps.games.igdb.client.time.sleep")
    @patch("apps.games.igdb.client._build_session")
    def test_paginate_multiple_pages(self, mock_build: MagicMock, mock_sleep: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}

        # Page 1: full page (500 items), Page 2: partial (10 items)
        page1_resp = MagicMock()
        page1_resp.status_code = 200
        page1_resp.raise_for_status.return_value = None
        page1_resp.json.return_value = [{"id": i} for i in range(500)]

        page2_resp = MagicMock()
        page2_resp.status_code = 200
        page2_resp.raise_for_status.return_value = None
        page2_resp.json.return_value = [{"id": i} for i in range(10)]

        session.post.side_effect = [token_resp, page1_resp, page2_resp]
        mock_build.return_value = session
        client = IgdbClient()
        pages = list(client.iter_genres())
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(pages[0]), 500)
        self.assertEqual(len(pages[1]), 10)

    @patch("apps.games.igdb.client.time.sleep")
    @patch("apps.games.igdb.client._build_session")
    def test_paginate_rate_limit_retry(self, mock_build: MagicMock, mock_sleep: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}

        # First API call: 429, then retry succeeds
        rate_resp = MagicMock()
        rate_resp.status_code = 429
        rate_resp.headers = {"Retry-After": "1"}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.raise_for_status.return_value = None
        ok_resp.json.return_value = [{"id": 1}]

        session.post.side_effect = [token_resp, rate_resp, ok_resp]
        mock_build.return_value = session
        client = IgdbClient()
        with self.assertLogs("apps.games.igdb.client", level="WARNING"):
            pages = list(client.iter_genres())
        self.assertEqual(len(pages), 1)
        mock_sleep.assert_called()


@override_settings(IGDB_CLIENT_ID="test_id", IGDB_CLIENT_SECRET="test_secret")
class GetIgdbClientTests(TestCase):
    @patch("apps.games.igdb.client._build_session")
    def test_singleton(self, mock_build: MagicMock) -> None:
        session = MagicMock()
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "tok"}
        session.post.return_value = token_resp
        mock_build.return_value = session

        # Reset singleton
        import apps.games.igdb.client as client_module

        client_module._client_instance = None
        c1 = get_igdb_client()
        c2 = get_igdb_client()
        self.assertIs(c1, c2)
        # Cleanup
        client_module._client_instance = None
