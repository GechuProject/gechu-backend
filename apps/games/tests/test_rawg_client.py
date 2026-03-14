from typing import Any
from unittest import TestCase
from unittest.mock import Mock, patch

from requests.models import Response

from apps.games.rawg.client import RawgClient
from apps.games.rawg.exceptions import RawgNotFoundError, RawgRateLimitError, RawgServerError


def mock_response(status_code: int, json_data: dict[str, Any] | None = None) -> Response:
    """Mock Response 객체 생성"""
    response = Mock(spec=Response)
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.raise_for_status.side_effect = None if status_code < 400 else Exception("HTTP Error")
    return response


class RawgClientTests(TestCase):
    def setUp(self) -> None:
        self.client = RawgClient()

    # -----------------------------
    # get_game_detail 테스트
    # -----------------------------
    def test_get_game_detail_success(self) -> None:
        data = {"id": 1, "name": "Test Game"}
        with patch.object(self.client._session, "get", return_value=mock_response(200, data)):
            result = self.client.get_game_detail(1)
            self.assertEqual(result, data)

    def test_get_game_detail_404(self) -> None:
        with patch.object(self.client._session, "get", return_value=mock_response(404)):
            with self.assertRaises(RawgNotFoundError):
                self.client.get_game_detail(999)

    def test_get_game_detail_429(self) -> None:
        with patch.object(self.client._session, "get", return_value=mock_response(429)):
            with self.assertRaises(RawgRateLimitError):
                self.client.get_game_detail(1)

    def test_get_game_detail_500(self) -> None:
        with patch.object(self.client._session, "get", return_value=mock_response(500)):
            with self.assertRaises(RawgServerError):
                self.client.get_game_detail(1)

    # -----------------------------
    # get_game_screenshots 테스트
    # -----------------------------
    def test_get_game_screenshots_success(self) -> None:
        data = {"results": [{"id": 1}, {"id": 2}]}
        with patch.object(self.client._session, "get", return_value=mock_response(200, data)):
            results = self.client.get_game_screenshots(1)
            self.assertEqual(results, data["results"])

    # -----------------------------
    # get_game_trailers 테스트
    # -----------------------------
    def test_get_game_trailers_success(self) -> None:
        data = {"results": [{"id": 10}]}
        with patch.object(self.client._session, "get", return_value=mock_response(200, data)):
            results = self.client.get_game_trailers(1)
            self.assertEqual(results, data["results"])

    # -----------------------------
    # _paginate 테스트
    # -----------------------------
    @patch.object(RawgClient, "_get")
    def test_paginate_multiple_pages(self, mock_get: Mock) -> None:
        mock_get.side_effect = [
            {"results": [{"id": 1}, {"id": 2}], "next": "next_url"},
            {"results": [{"id": 3}], "next": None},
        ]
        results = list(self.client._paginate("games"))
        self.assertEqual([r["id"] for r in results], [1, 2, 3])

    @patch.object(RawgClient, "_get")
    def test_paginate_empty_results(self, mock_get: Mock) -> None:
        mock_get.return_value = {"results": [], "next": None}
        results = list(self.client._paginate("games"))
        self.assertEqual(results, [])

    # -----------------------------
    # iter_* 메서드 테스트
    # -----------------------------
    @patch.object(RawgClient, "_paginate")
    def test_iter_games(self, mock_paginate: Mock) -> None:
        mock_paginate.return_value = iter([{"id": 1}, {"id": 2}])
        results = list(self.client.iter_games())
        self.assertEqual([r["id"] for r in results], [1, 2])

    @patch.object(RawgClient, "_paginate")
    def test_iter_genres(self, mock_paginate: Mock) -> None:
        mock_paginate.return_value = iter([{"id": 10}])
        results = list(self.client.iter_genres())
        self.assertEqual([r["id"] for r in results], [10])

    @patch.object(RawgClient, "_paginate")
    def test_iter_platforms(self, mock_paginate: Mock) -> None:
        mock_paginate.return_value = iter([{"id": 20}])
        results = list(self.client.iter_platforms())
        self.assertEqual([r["id"] for r in results], [20])

    @patch.object(RawgClient, "_paginate")
    def test_iter_tags(self, mock_paginate: Mock) -> None:
        mock_paginate.return_value = iter([{"id": 30}])
        results = list(self.client.iter_tags())
        self.assertEqual([r["id"] for r in results], [30])

    @patch.object(RawgClient, "_paginate")
    def test_iter_stores(self, mock_paginate: Mock) -> None:
        mock_paginate.return_value = iter([{"id": 40}])
        results = list(self.client.iter_stores())
        self.assertEqual([r["id"] for r in results], [40])
