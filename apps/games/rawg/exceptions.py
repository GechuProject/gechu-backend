# 우리 서비스에서 사용하는 exception
"""
RAWG API 관련 예외 클래스
"""


# TODO: 필요 시 RawgException, RawgRateLimitError, RawgNotFoundError, RawgServerError, RawgSyncError 만들어주세요
class RawgException(Exception):
    # RAWG API 관련 기본 예외
    pass


class RawgRateLimitError(RawgException):
    # RAWG API 호출 시 Rate Limit 초과
    pass


class RawgNotFoundError(RawgException):
    # 데이터 없을 때 (404)
    pass


class RawgServerError(RawgException):
    # RAWG API 서버 에러 (5xx)
    pass


class RawgSyncError(RawgException):
    # RAWG 데이터 동기화 중 발생한 서비스 레이어 예외
    pass