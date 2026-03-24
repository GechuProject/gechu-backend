from __future__ import annotations

from rest_framework.test import APIClient

from apps.users.models import User
from apps.users.services.auth_service import issue_auth_tokens


def make_cookie_client() -> APIClient:
    return APIClient(enforce_csrf_checks=True)


def attach_csrf(client: APIClient) -> str:
    response = client.get("/api/v1/auth/csrf/")
    if response.status_code != 200:
        raise AssertionError(f"Failed to issue CSRF token: {response.status_code}")

    csrf_token = str(response.json()["csrf_token"])
    client.credentials(HTTP_X_CSRFTOKEN=csrf_token)
    return csrf_token


def authenticate_client_with_cookies(client: APIClient, user: User) -> None:
    attach_csrf(client)
    access_token, refresh_token, _ = issue_auth_tokens(user)
    client.cookies["access_token"] = access_token
    client.cookies["refresh_token"] = refresh_token
