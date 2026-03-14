# 우리 서비스에서 사용하는 exception
"""
RAWG API 관련 예외 클래스
"""


# TODO: 필요 시 RawgException, RawgRateLimitError, RawgNotFoundError, RawgServerError, RawgSyncError 만들어주세요
class RawgException(Exception):
    # RAWG API 관련 기본 예외
    default_message: str = "RAWG API 오류가 발생했습니다."

    def __init__(self, message: str | None = None, status: int | None = None):
        if status:
            message = message or f"{self.default_message} (status: {status})"
        super().__init__(message)


class RawgRateLimitError(RawgException):
    # RAWG API 호출 시 Rate Limit 초과 (429)
    default_message = "RAWG API Rate Limit을 초과했습니다."


class RawgNotFoundError(RawgException):
    # 데이터 없을 때 (404)
    default_message = "RAWG API에서 데이터를 찾을 수 없습니다."


class RawgServerError(RawgException):
    # RAWG API 서버 에러 (5xx)
    default_message = "RAWG API 서버 오류가 발생했습니다."


class RawgSyncError(RawgException):
    # RAWG 데이터 동기화 중 발생한 서비스 레이어 예외
    default_message = "RAWG 데이터 동기화 중 오류가 발생했습니다."
