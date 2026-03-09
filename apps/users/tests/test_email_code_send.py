from typing import cast
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.response import Response
from rest_framework.test import APIClient


class EmailCodeSendAPITest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.email = "user@example.com"
        # 테스트 간 간섭 방지
        cache.delete(f"email_code:{self.email}")
        cache.delete(f"email_code_cooldown:{self.email}")

    @patch("apps.users.views.auth.send_mail")
    def test_send_email_code_stores_code_in_cache(self, mock_send_mail: MagicMock) -> None:
        res = self.client.post(
            "/api/v1/auth/email/code/",
            data={"email": self.email},
            format="json",
        )

        drf_res = cast(Response, res)

        self.assertEqual(drf_res.status_code, 201)
        self.assertEqual(drf_res.data.get("message"), "인증 코드가 발송되었습니다.")
        self.assertEqual(drf_res.data.get("expires_in"), 300)

        code = cache.get(f"email_code:{self.email}")
        self.assertIsNotNone(code)
        self.assertEqual(len(str(code)), 6)
        self.assertTrue(str(code).isdigit())
        mock_send_mail.assert_called_once()
