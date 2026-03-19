from typing import cast
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient


@override_settings(
    DISCORD_AUTHORIZE_URL="https://discord.example.com/oauth2/authorize",
    DISCORD_CLIENT_ID="discord-client-id",
    DISCORD_REDIRECT_URI="https://example.com/auth/discord/callback/",
)
class DiscordLoginAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        self.url = reverse("auth-discord-login")

    def test_discord_login_redirects_to_discord_oauth_and_saves_state(self) -> None:
        response = self.client.get(self.url)
        redirect_response = cast(HttpResponseRedirect, response)

        parsed_url = urlparse(redirect_response.url)
        query_params = parse_qs(parsed_url.query)
        state = query_params["state"][0]

        self.assertEqual(parsed_url.scheme, "https")
        self.assertEqual(parsed_url.netloc, "discord.example.com")
        self.assertEqual(parsed_url.path, "/oauth2/authorize")
        self.assertEqual(query_params["client_id"][0], "discord-client-id")
        self.assertEqual(query_params["redirect_uri"][0], "https://example.com/auth/discord/callback/")
        self.assertEqual(query_params["response_type"][0], "code")
        self.assertEqual(query_params["scope"][0], "identify email")
        self.assertEqual(cache.get(f"oauth_state:{state}"), "discord")
