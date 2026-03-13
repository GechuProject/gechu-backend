import secrets
from datetime import date
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.social_user import SocialUser
from apps.users.models.user import User
from apps.users.services.auth_service import get_active_user_or_deactivated, issue_auth_tokens
from apps.users.services.nickname_service import generate_unique_nickname

# Provider가 생년월일 정보를 주지 않는 경우 소셜 가입 기본값을 사용합니다.
DEFAULT_SOCIAL_BIRTH_DATE = date(2000, 1, 1)


def build_kakao_login_url() -> str:
    state = secrets.token_urlsafe(32)
    cache.set(f"oauth_state:kakao:{state}", True, timeout=300)

    params = {
        "client_id": settings.KAKAO_CLIENT_ID,
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
        "response_type": "code",
        "state": state,
    }

    query_string = urlencode(params)
    return f"https://kauth.kakao.com/oauth/authorize?{query_string}"


def handle_kakao_callback(*, code: str, state: str) -> dict[str, object]:
    saved_state = cache.get(f"oauth_state:kakao:{state}")
    if saved_state is None:
        raise CustomAPIException(ErrorMessages.INVALID_STATE)

    cache.delete(f"oauth_state:kakao:{state}")
    kakao_access_token = request_kakao_access_token(code=code)
    user_info = request_kakao_user_info(access_token=kakao_access_token)
    provider_uid, email, birth_date = extract_kakao_user_data(user_info)
    user, is_new_user = get_or_create_kakao_user(
        provider_uid=provider_uid,
        email=email,
        birth_date=birth_date,
    )
    service_access_token, refresh_token, expires_in = issue_auth_tokens(user)

    return {
        "access_token": service_access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "is_new_user": is_new_user,
    }


def request_kakao_access_token(*, code: str) -> str:
    try:
        response = requests.post(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.KAKAO_CLIENT_ID,
                "redirect_uri": settings.KAKAO_REDIRECT_URI,
                "client_secret": settings.KAKAO_CLIENT_SECRET,
                "code": code,
            },
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR) from err

    payload = response.json()
    access_token = payload.get("access_token")
    if not isinstance(access_token, str):
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    return access_token


def request_kakao_user_info(*, access_token: str) -> dict[str, object]:
    try:
        response = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR) from err

    payload = response.json()
    if not isinstance(payload, dict):
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    return payload


def extract_kakao_user_data(user_info: dict[str, object]) -> tuple[str, str | None, date]:
    provider_uid = user_info.get("id")
    if provider_uid is None:
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    kakao_account = user_info.get("kakao_account", {})
    email = None
    birth_date = DEFAULT_SOCIAL_BIRTH_DATE

    if isinstance(kakao_account, dict):
        raw_email = kakao_account.get("email")
        if isinstance(raw_email, str):
            email = raw_email

        birthyear = kakao_account.get("birthyear")
        birthday = kakao_account.get("birthday")

        if isinstance(birthyear, str) and isinstance(birthday, str) and len(birthday) == 4:
            month = int(birthday[:2])
            day = int(birthday[2:])
            birth_date = date(int(birthyear), month, day)

    return str(provider_uid), email, birth_date


def get_or_create_kakao_user(*, provider_uid: str, email: str | None, birth_date: date) -> tuple[User, bool]:
    social_user = (
        SocialUser.objects.filter(
            provider=SocialUser.Provider.KAKAO,
            provider_uid=provider_uid,
        )
        .select_related("user")
        .first()
    )

    if social_user is not None:
        get_active_user_or_deactivated(social_user.user)
        return social_user.user, False

    if email is None:
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    existing_user = User.objects.filter(email=email).first()
    if existing_user is not None:
        get_active_user_or_deactivated(existing_user)
        SocialUser.objects.create(
            user=existing_user,
            provider=SocialUser.Provider.KAKAO,
            provider_uid=provider_uid,
        )
        return existing_user, False

    for _ in range(5):
        nickname = generate_unique_nickname()
        try:
            user = User.objects.create_user(
                email=email,
                nickname=nickname,
                birth_date=birth_date,
                password=None,
            )
            break
        except IntegrityError:
            continue
    else:
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    SocialUser.objects.create(
        user=user,
        provider=SocialUser.Provider.KAKAO,
        provider_uid=provider_uid,
    )

    return user, True
