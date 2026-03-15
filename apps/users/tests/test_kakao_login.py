from typing import cast

from django.http import HttpResponseRedirect
from django.test import TestCase
from rest_framework.test import APIClient


class KakaoLoginAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_kakao_login_redirects_to_kakao_oauth(self) -> None:
        response = self.client.get("/api/v1/auth/kakao/login/")
        redirect_response = cast(HttpResponseRedirect, response)

        self.assertIn("https://kauth.kakao.com/oauth/authorize", redirect_response.url)
        self.assertIn("client_id=", redirect_response.url)
        self.assertIn("redirect_uri=", redirect_response.url)
        self.assertIn("response_type=code", redirect_response.url)
        self.assertIn("state=", redirect_response.url)
