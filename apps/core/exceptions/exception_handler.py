import logging
import os
from typing import Any, cast

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.core.exceptions.exception_message import ErrorMessages

logger = logging.getLogger(__name__)


class CustomAPIException(APIException):
    def __init__(self, error: ErrorMessages):
        self.status_code = error.status_code
        self.detail = cast(
            dict[str, Any],
            {
                "status_code": error.status_code,
                "code": error.name,
                "message": error.message,
            },
        )


def custom_exception_handler(
    exc: Exception,
    context: dict[str, Any],
) -> Response | None:
    """
    DRF 기본 exception_handler를 커스터마이징
    CustomAPIException을 포함한 모든 APIException 처리 가능
    """
    # 먼저 DRF 기본 처리 시도
    response = exception_handler(exc, context)

    if response is not None:
        return response

    # APIException을 상속하지 않는 커스텀 예외 처리
    if hasattr(exc, "detail") and hasattr(exc, "status_code"):
        status_code = getattr(exc, "status_code", status.HTTP_400_BAD_REQUEST)
        if status_code >= 500:
            logger.warning("API exception: %s", exc.detail)
        return Response(data=exc.detail, status=status_code)

    # IGDB 예외 처리
    from apps.games.igdb.exceptions import IgdbNotFoundError, IgdbRateLimitError, IgdbServerError

    if isinstance(exc, IgdbNotFoundError):
        return Response(
            data={"status_code": 404, "code": "GAME_NOT_FOUND", "message": "게임을 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if isinstance(exc, IgdbRateLimitError):
        return Response(
            data={"status_code": 503, "code": "SERVICE_UNAVAILABLE", "message": "잠시 후 다시 시도해주세요."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if isinstance(exc, IgdbServerError):
        return Response(
            data={"status_code": 502, "code": "BAD_GATEWAY", "message": "외부 API 오류가 발생했습니다."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # 그 외 예외는 500으로 처리
    logger.exception("Unhandled exception occurred")
    error_message = "서버 오류가 발생했습니다."

    # DEBUG = True일 때는 실제 에러 메시지 노출
    if os.getenv("DJANGO_SETTINGS_MODULE") != "config.settings.prod":
        error_message = f"{str(exc)}"

    return Response(
        data={
            "status_code": 500,
            "code": "SERVER_ERROR",
            "message": error_message,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
