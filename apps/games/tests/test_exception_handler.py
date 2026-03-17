from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import NotFound

from apps.core.exceptions.exception_handler import CustomAPIException, custom_exception_handler
from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.igdb.exceptions import IgdbNotFoundError, IgdbRateLimitError, IgdbServerError


def _context():
    """Minimal DRF exception handler context."""
    return {"view": MagicMock(), "request": MagicMock()}


class CustomAPIExceptionTests(TestCase):
    def test_creates_with_error_messages(self):
        exc = CustomAPIException(ErrorMessages.GAME_NOT_FOUND)
        self.assertEqual(exc.status_code, 404)
        self.assertEqual(exc.detail["code"], "GAME_NOT_FOUND")
        self.assertIn("게임", exc.detail["message"])


class CustomExceptionHandlerTests(TestCase):
    def test_drf_exception_handled(self):
        exc = NotFound("not found")
        response = custom_exception_handler(exc, _context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)

    def test_igdb_not_found_returns_404(self):
        exc = IgdbNotFoundError("game not found")
        response = custom_exception_handler(exc, _context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "GAME_NOT_FOUND")

    def test_igdb_rate_limit_returns_503(self):
        exc = IgdbRateLimitError(retry_after=5)
        response = custom_exception_handler(exc, _context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "SERVICE_UNAVAILABLE")

    def test_igdb_server_error_returns_502(self):
        exc = IgdbServerError(status_code=502)
        response = custom_exception_handler(exc, _context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["code"], "BAD_GATEWAY")

    def test_generic_exception_returns_500(self):
        exc = RuntimeError("unexpected")
        response = custom_exception_handler(exc, _context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["code"], "SERVER_ERROR")

    @patch.dict("os.environ", {"DJANGO_SETTINGS_MODULE": "config.settings.prod"})
    def test_generic_exception_hides_detail_in_prod(self):
        exc = RuntimeError("secret info")
        response = custom_exception_handler(exc, _context())
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret info", response.data["message"])
        self.assertIn("서버 오류", response.data["message"])

    @patch.dict("os.environ", {"DJANGO_SETTINGS_MODULE": "config.settings.dev"})
    def test_generic_exception_shows_detail_in_dev(self):
        exc = RuntimeError("debug info")
        response = custom_exception_handler(exc, _context())
        self.assertEqual(response.status_code, 500)
        self.assertIn("debug info", response.data["message"])

    def test_exception_with_detail_and_status_code_attrs(self):
        """Test non-DRF exception that has detail and status_code attributes."""
        exc = Exception("test")
        exc.detail = {"status_code": 400, "code": "CUSTOM", "message": "custom error"}
        exc.status_code = 400
        response = custom_exception_handler(exc, _context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "CUSTOM")

    def test_custom_api_exception_handled(self):
        exc = CustomAPIException(ErrorMessages.VALIDATION_ERROR)
        response = custom_exception_handler(exc, _context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 400)
