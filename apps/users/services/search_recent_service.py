from __future__ import annotations

from django.conf import settings
from django_redis import get_redis_connection

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User
from apps.users.services.user_me_service import get_user_me


def _recent_search_key(*, user_id: int) -> str:
    return f"search:recent:{user_id}"


def save_recent_search_keyword(*, user: User, keyword: str) -> None:
    user = get_user_me(user)
    connection = get_redis_connection("default")
    key = _recent_search_key(user_id=user.id)
    with connection.pipeline() as pipe:
        pipe.lrem(key, 0, keyword)
        pipe.lpush(key, keyword)
        pipe.ltrim(key, 0, settings.SEARCH_HISTORY_MAX_SIZE - 1)
        pipe.execute()


def get_recent_searches(*, user: User) -> dict[str, object]:
    user = get_user_me(user)
    connection = get_redis_connection("default")
    raw_keywords = connection.lrange(_recent_search_key(user_id=user.id), 0, settings.SEARCH_HISTORY_MAX_SIZE - 1)
    keywords = [keyword.decode("utf-8") if isinstance(keyword, bytes) else str(keyword) for keyword in raw_keywords]
    return {"results": keywords}


def clear_recent_searches(*, user: User) -> dict[str, object]:
    user = get_user_me(user)
    connection = get_redis_connection("default")
    connection.delete(_recent_search_key(user_id=user.id))
    return {"message": "최근 검색어가 모두 삭제되었습니다."}


def delete_recent_search_keyword(*, user: User, keyword: str) -> dict[str, object]:
    user = get_user_me(user)
    connection = get_redis_connection("default")
    removed_count = connection.lrem(_recent_search_key(user_id=user.id), 0, keyword)
    if removed_count == 0:
        raise CustomAPIException(ErrorMessages.SEARCH_KEYWORD_NOT_FOUND)
    return {"message": "검색어가 삭제되었습니다."}
