"""
IGDB API 관련 예외 클래스

계층 구조:
    IgdbException
    ├── IgdbAuthError       (401 - 토큰 만료/무효)
    ├── IgdbRateLimitError  (429 - Too Many Requests)
    ├── IgdbNotFoundError   (404 - Not Found)
    └── IgdbServerError     (5xx - Server Error)
    IgdbSyncError           (DB 동기화 중 발생하는 비-HTTP 오류)
"""

from __future__ import annotations


class IgdbException(Exception):
    """IGDB API 관련 모든 예외의 베이스 클래스"""

    pass


class IgdbAuthError(IgdbException):
    """
    HTTP 401 Unauthorized
    토큰이 만료되었거나 Client ID/Secret이 잘못된 경우.
    클라이언트에서 토큰 재발급 후 재시도해야 합니다.
    """

    pass


class IgdbRateLimitError(IgdbException):
    """
    HTTP 429 Too Many Requests
    IGDB 무료 티어: 4 req/s 제한.
    Retry-After 헤더값(초)을 retry_after 속성으로 보관합니다.
    """

    def __init__(self, message: str = "IGDB rate limit 초과", retry_after: int = 1) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class IgdbNotFoundError(IgdbException):
    """HTTP 404 Not Found"""

    pass


class IgdbServerError(IgdbException):
    """HTTP 5xx Server Error"""

    def __init__(self, message: str = "IGDB 서버 오류", status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class IgdbSyncError(IgdbException):
    """
    DB 동기화 중 발생하는 비-HTTP 오류
    예) 컨버터 변환 실패, 필수 FK 누락 등
    """

    pass
