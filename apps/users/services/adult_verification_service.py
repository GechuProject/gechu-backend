import base64
import secrets
from datetime import date, timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models import AdultVerification, User
from apps.users.services.auth_service import get_active_user_or_deactivated

ADULT_VERIFICATION_STATE_TTL_SECONDS = 300
ADULT_VERIFICATION_TTL_DAYS = 365


def initiate_adult_verification(*, user: User) -> str:
    authorize_url = getattr(settings, "BBATON_AUTHORIZE_URL", None)
    client_id = getattr(settings, "BBATON_CLIENT_ID", None)
    redirect_uri = getattr(settings, "BBATON_REDIRECT_URI", None)

    if not authorize_url or not client_id or not redirect_uri:
        raise CustomAPIException(ErrorMessages.SERVER_ERROR)

    state = secrets.token_urlsafe(32)
    cache.set(
        f"adult_verification_state:{state}",
        {"user_id": user.id},
        timeout=ADULT_VERIFICATION_STATE_TTL_SECONDS,
    )

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "read_profile",
        "state": state,
    }
    return f"{authorize_url}?{urlencode(params)}"


def complete_adult_verification(*, code: str, state: str) -> dict[str, object]:
    cached_state = cache.get(f"adult_verification_state:{state}")
    if not isinstance(cached_state, dict) or "user_id" not in cached_state:
        raise CustomAPIException(ErrorMessages.INVALID_STATE)

    cache.delete(f"adult_verification_state:{state}")

    user = User.objects.filter(id=cached_state["user_id"]).first()
    if user is None:
        raise CustomAPIException(ErrorMessages.USER_NOT_FOUND)
    user = get_active_user_or_deactivated(user)

    if _is_adult_verification_valid(user):
        raise CustomAPIException(ErrorMessages.ALREADY_VERIFIED)

    access_token = _request_bbaton_access_token(code=code)
    user_info = _request_bbaton_user_info(access_token=access_token)
    provider_uid, adult_flag, birth_year = _extract_bbaton_verification_data(user_info)

    if adult_flag != "Y" or not _is_over_18(user.birth_date, birth_year):
        raise CustomAPIException(ErrorMessages.UNDERAGE)

    if AdultVerification.objects.filter(
        provider=AdultVerification.Provider.BBATON,
        provider_uid=provider_uid,
    ).exclude(user=user).exists():
        raise CustomAPIException(ErrorMessages.VERIFICATION_ALREADY_USED)

    verified_at = timezone.now()
    expires_at = verified_at + timedelta(days=ADULT_VERIFICATION_TTL_DAYS)

    AdultVerification.objects.create(
        user=user,
        provider=AdultVerification.Provider.BBATON,
        provider_uid=provider_uid,
        raw_payload=user_info,
        verified_at=verified_at,
        expires_at=expires_at,
    )

    user.is_adult_verified = True
    user.adult_verified_at = verified_at
    user.adult_verification_expires_at = expires_at
    user.save(
        update_fields=[
            "is_adult_verified",
            "adult_verified_at",
            "adult_verification_expires_at",
            "updated_at",
        ]
    )

    return {
        "is_adult_verified": True,
        "adult_verified_at": verified_at,
        "expires_at": expires_at,
    }


def get_adult_verification_status(*, user: User) -> dict[str, object]:
    expires_at = user.adult_verification_expires_at
    is_valid = _is_adult_verification_valid(user)

    return {
        "is_adult_verified": is_valid,
        "adult_verified_at": user.adult_verified_at,
        "adult_verified_until": expires_at,
    }


def _is_adult_verification_valid(user: User) -> bool:
    expires_at = user.adult_verification_expires_at
    if user.is_adult_verified is False or expires_at is None:
        return False
    return timezone.now() < expires_at


def _request_bbaton_access_token(*, code: str) -> str:
    token_url = getattr(settings, "BBATON_TOKEN_URL", None)
    client_id = getattr(settings, "BBATON_CLIENT_ID", None)
    client_secret = getattr(settings, "BBATON_CLIENT_SECRET", None)
    redirect_uri = getattr(settings, "BBATON_REDIRECT_URI", None)

    if not token_url or not client_id or not client_secret or not redirect_uri:
        raise CustomAPIException(ErrorMessages.SERVER_ERROR)

    basic_token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")

    try:
        response = requests.post(
            token_url,
            headers={
                "Authorization": f"Basic {basic_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
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


def _request_bbaton_user_info(*, access_token: str) -> dict[str, object]:
    user_info_url = getattr(settings, "BBATON_USER_INFO_URL", None)
    if not user_info_url:
        raise CustomAPIException(ErrorMessages.SERVER_ERROR)

    try:
        response = requests.get(
            user_info_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR) from err

    payload = response.json()
    if not isinstance(payload, dict):
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    return payload


def _extract_bbaton_verification_data(user_info: dict[str, object]) -> tuple[str, str, str | None]:
    provider_uid = user_info.get("user_id")
    adult_flag = user_info.get("adult_flag")
    birth_year = user_info.get("birth_year")

    if not isinstance(provider_uid, str) or not isinstance(adult_flag, str):
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    if birth_year is not None and not isinstance(birth_year, str):
        raise CustomAPIException(ErrorMessages.OAUTH_CALLBACK_ERROR)

    return provider_uid, adult_flag, birth_year


def _is_over_18(birth_date: date, birth_year: str | None = None) -> bool:
    if birth_year is not None and birth_year.isdigit():
        return timezone.localdate().year - int(birth_year) >= 18

    today = timezone.localdate()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age >= 18
