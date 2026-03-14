"""
RAWG API 관련 예외 클래스

계층 구조:
    RawgException
    ├── RawgRateLimitError   (HTTP 429 - Too Many Requests)
    ├── RawgNotFoundError    (HTTP 404 - Not Found)
    └── RawgServerError      (HTTP 5xx - Server Error)

    RawgSyncError            (DB 동기화 중 발생하는 비-HTTP 오류)
"""


class RawgException(Exception):
    """RAWG API 관련 모든 예외의 베이스 클래스"""


class RawgRateLimitError(RawgException):
    """
    HTTP 429 Too Many Requests
    Retry-After 헤더 값(초)을 retry_after 속성으로 보관합니다.
    Celery 태스크에서 이 값을 countdown으로 사용합니다.
    """

    def __init__(self, message: str = "RAWG rate limit 초과", retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RawgNotFoundError(RawgException):
    """HTTP 404 Not Found. 존재하지 않는 게임 ID 조회 시 발생"""


class RawgServerError(RawgException):
    """HTTP 5xx Server Error. autoretry_for 대상"""

    def __init__(self, message: str = "RAWG 서버 오류", status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class RawgSyncError(RawgException):
    """
    DB 동기화 중 발생하는 비-HTTP 오류
    예) 컨버터 변환 실패, 필수 FK 누락 등
    """
