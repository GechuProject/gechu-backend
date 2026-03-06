from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException, ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.core.exceptions.exception_message import ErrorMessages


class CustomAPIException(APIException):
    def __init__(self, error: ErrorMessages):
        self.status_code = error.status_code
        self.detail = {
            "status_code": ErrorDetail(str(error.status_code)),
            "code": ErrorDetail(str(error.name)),
            "message": ErrorDetail(str(error.message)),
        }


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
        return Response(
            data=exc.detail,
            status=getattr(exc, "status_code", status.HTTP_400_BAD_REQUEST),
        )

    # 그 외 예외는 500으로 처리
    return Response(
        data={
            "status_code": 500,
            "code": "SERVER_ERROR",
            "message": "서버 오류가 발생했습니다.",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
