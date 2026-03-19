import logging
import secrets
from datetime import date
from urllib.parse import urlencode
from uuid import uuid4

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.social_user import SocialUser
from apps.users.models.user import User
from apps.users.services.auth_service import get_active_user_or_deactivated, issue_auth_tokens
from apps.users.services.nickname_service import generate_unique_nickname

logger = logging.getLogger(__name__)

# Providers like Discord do not expose birth date, so we keep a safe default.
DEFAULT_SOCIAL_BIRTH_DATE = date(2000, 1, 1)

_FRONTEND_CALLBACK_URL = f"{settings.FRONTEND_DOMAIN}/auth/callback"

_OAUTH_STATE_CACHE_TIMEOUT = 600
_NICKNAME_MAX_RETRIES = 5


def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def build_social_success_redirect_url(*, is_new_user: bool) -> str:
    return f"{_FRONTEND_CALLBACK_URL}?{urlencode({'is_new_user': str(is_new_user).lower()})}"


def build_social_error_redirect_url(*, error: str, error_description: str) -> str:
    return f"{_FRONTEND_CALLBACK_URL}?{urlencode({'error': error, 'error_description': error_description})}"


def build_kakao_login_url() -> str:
    state = secrets.token_urlsafe(32)
    cache.set(f"oauth_state:{state}", "kakao", timeout=_OAUTH_STATE_CACHE_TIMEOUT)

    params = {
        "client_id": settings.KAKAO_CLIENT_ID,
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
        "response_type": "code",
        "state": state,
    }
    return f"{settings.KAKAO_AUTHORIZE_URL}?{urlencode(params)}"


def build_discord_login_url() -> str:
    state = secrets.token_urlsafe(32)
    cache.set(f"oauth_state:{state}", "discord", timeout=_OAUTH_STATE_CACHE_TIMEOUT)

    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email",
        "state": state,
    }
    return f"{settings.DISCORD_AUTHORIZE_URL}?{urlencode(params)}"


def handle_kakao_callback(*, code: str, state: str) -> dict[str, object]:
    _validate_oauth_state(state=state, expected_provider="kakao")
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


def handle_discord_callback(*, code: str, state: str) -> dict[str, object]:
    _validate_oauth_state(state=state, expected_provider="discord")
    discord_access_token = request_discord_access_token(code=code)
    user_info = request_discord_user_info(access_token=discord_access_token)
    provider_uid, email, birth_date = extract_discord_user_data(user_info)
    user, is_new_user = get_or_create_discord_user(
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


def _validate_oauth_state(*, state: str, expected_provider: str) -> None:
    provider = cache.get(f"oauth_state:{state}")
    if provider != expected_provider:
        raise CustomAPIException(ErrorMessages.INVALID_STATE)
    cache.delete(f"oauth_state:{state}")


def request_kakao_access_token(*, code: str) -> str:
    try:
        session = _make_session()
        response = session.post(
            settings.KAKAO_TOKEN_URL,
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
        logger.exception("카카오 액세스 토큰 요청 실패: %s", err)
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR) from err

    payload = response.json()
    access_token = payload.get("access_token")
    if not isinstance(access_token, str):
        logger.error("카카오 액세스 토큰 응답 이상: %s", payload)
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    return access_token


def request_discord_access_token(*, code: str) -> str:
    try:
        session = _make_session()
        response = session.post(
            settings.DISCORD_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.DISCORD_CLIENT_ID,
                "client_secret": settings.DISCORD_CLIENT_SECRET,
                "redirect_uri": settings.DISCORD_REDIRECT_URI,
                "code": code,
            },
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        logger.exception("디스코드 액세스 토큰 요청 실패: %s", err)
        raise CustomAPIException(ErrorMessages.DISCORD_OAUTH_CALLBACK_ERROR) from err

    payload = response.json()
    access_token = payload.get("access_token")
    if not isinstance(access_token, str):
        logger.error("디스코드 액세스 토큰 응답 이상: %s", payload)
        raise CustomAPIException(ErrorMessages.DISCORD_OAUTH_CALLBACK_ERROR)

    return access_token


def request_kakao_user_info(*, access_token: str) -> dict[str, object]:
    try:
        session = _make_session()
        response = session.get(
            settings.KAKAO_USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        logger.exception("카카오 유저 정보 요청 실패: %s", err)
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR) from err

    payload = response.json()
    if not isinstance(payload, dict):
        logger.error("카카오 유저 정보 응답 이상: %s", payload)
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    return payload


def request_discord_user_info(*, access_token: str) -> dict[str, object]:
    try:
        session = _make_session()
        response = session.get(
            settings.DISCORD_USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        logger.exception("디스코드 유저 정보 요청 실패: %s", err)
        raise CustomAPIException(ErrorMessages.DISCORD_OAUTH_CALLBACK_ERROR) from err

    payload = response.json()
    if not isinstance(payload, dict):
        logger.error("디스코드 유저 정보 응답 이상: %s", payload)
        raise CustomAPIException(ErrorMessages.DISCORD_OAUTH_CALLBACK_ERROR)

    return payload


def extract_kakao_user_data(user_info: dict[str, object]) -> tuple[str, str, date]:
    provider_uid = user_info.get("id")
    if provider_uid is None:
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    provider_uid_str = str(provider_uid)
    kakao_account = user_info.get("kakao_account", {})
    # 카카오는 이메일 제공을 거부할 수 있으므로 fallback 사용
    email = f"kakao_{provider_uid_str}@social.gechu"
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

    return provider_uid_str, email, birth_date


def extract_discord_user_data(user_info: dict[str, object]) -> tuple[str, str, date]:
    provider_uid = user_info.get("id")
    email = user_info.get("email")

    if not isinstance(provider_uid, str) or not isinstance(email, str):
        raise CustomAPIException(ErrorMessages.DISCORD_OAUTH_CALLBACK_ERROR)

    return provider_uid, email, DEFAULT_SOCIAL_BIRTH_DATE


def get_or_create_kakao_user(*, provider_uid: str, email: str, birth_date: date) -> tuple[User, bool]:
    return _get_or_create_social_user(
        provider=SocialUser.Provider.KAKAO,
        provider_uid=provider_uid,
        email=email,
        birth_date=birth_date,
    )


def get_or_create_discord_user(*, provider_uid: str, email: str, birth_date: date) -> tuple[User, bool]:
    return _get_or_create_social_user(
        provider=SocialUser.Provider.DISCORD,
        provider_uid=provider_uid,
        email=email,
        birth_date=birth_date,
    )


def _get_or_create_social_user(
    *,
    provider: str,
    provider_uid: str,
    email: str,
    birth_date: date,
) -> tuple[User, bool]:
    social_user = SocialUser.objects.filter(provider=provider, provider_uid=provider_uid).select_related("user").first()

    if social_user is not None:
        get_active_user_or_deactivated(social_user.user)
        return social_user.user, False

    existing_user = User.objects.filter(email=email).first()
    if existing_user is not None:
        get_active_user_or_deactivated(existing_user)
        SocialUser.objects.get_or_create(
            user=existing_user,
            provider=provider,
            defaults={"provider_uid": provider_uid},
        )
        return existing_user, False

    user = _create_user_with_unique_nickname(email=email, birth_date=birth_date)
    SocialUser.objects.create(user=user, provider=provider, provider_uid=provider_uid)
    return user, True


def _create_user_with_unique_nickname(*, email: str, birth_date: date) -> User:
    for _ in range(_NICKNAME_MAX_RETRIES):
        nickname = generate_unique_nickname()
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    email=email,
                    nickname=nickname,
                    birth_date=birth_date,
                    password=None,
                )
        except IntegrityError:
            continue

    # UUID fallback
    uuid_nickname = str(uuid4()).replace("-", "")[:30]
    logger.warning("닉네임 생성 %d회 실패, UUID fallback 사용: %s", _NICKNAME_MAX_RETRIES, email)
    return User.objects.create_user(
        email=email,
        nickname=uuid_nickname,
        birth_date=birth_date,
        password=None,
    )
