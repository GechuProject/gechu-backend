from enum import Enum


class ErrorMessages(Enum):
    """
    에러 메시지와 HTTP 상태 코드를 함께 관리합니다.
    사용 예: raise CustomAPIException(ErrorMessages.INVALID_CODE)
    """

    # 400 Bad Request
    VALIDATION_ERROR = (400, "입력값이 올바르지 않습니다.")
    INVALID_QUERY_PARAM = (400, "유효하지 않은 쿼리 파라미터입니다.")
    INVALID_ORDERING = (400, "지원하지 않는 정렬 기준입니다.")
    INVALID_CODE = (400, "인증 코드가 올바르지 않습니다.")
    CODE_EXPIRED = (400, "인증 코드가 만료되었습니다.")
    SOCIAL_USER_ONLY = (400, "소셜 로그인 계정은 비밀번호 재설정을 지원하지 않습니다.")
    REFRESH_TOKEN_MISSING = (400, "refresh 토큰이 누락되었습니다.")
    INVALID_FILE_TYPE = (400, "지원하지 않는 파일 형식입니다. (jpg, jpeg, png, webp만 허용)")
    FILE_TOO_LARGE = (400, "파일 크기가 제한을 초과했습니다. (최대 5MB)")
    UNDERAGE = (400, "만 18세 미만은 성인 인증을 완료할 수 없습니다.")
    ALREADY_VERIFIED = (400, "이미 성인 인증이 완료된 계정입니다.")
    JOB_TYPE_MISSING = (400, "job_type이 누락되었습니다.")
    BASE_WEIGHT_INVALID = (400, "base_weight는 0보다 커야 합니다.")
    MULTIPLIER_INVALID = (400, "multiplier는 0보다 커야 합니다.")
    IS_VISIBLE_MISSING = (400, "is_visible 값이 누락되었습니다.")
    SEARCH_QUERY_MISSING = (400, "search_query가 누락되었습니다.")
    GAME_ID_OR_SOURCE_MISSING = (400, "game_id 또는 source가 누락되었습니다.")
    GAME_ID_OR_STORE_ID_MISSING = (400, "game_id 또는 store_id가 누락되었습니다.")
    GENRE_IDS_INVALID = (400, "genre_ids는 배열이어야 합니다.")
    INVALID_GENRE_ID = (400, "존재하지 않는 장르 ID가 포함되어 있습니다.")
    PLATFORM_IDS_INVALID = (400, "platform_ids는 배열이어야 합니다.")
    INVALID_PLATFORM_ID = (400, "존재하지 않는 플랫폼 ID가 포함되어 있습니다.")
    TAG_IDS_INVALID = (400, "tag_ids는 배열이어야 합니다.")
    INVALID_TAG_ID = (400, "존재하지 않는 태그 ID가 포함되어 있습니다.")
    INVALID_REACTION = (400, "reaction은 like, dislike, neutral 중 하나여야 합니다.")
    REACTION_DATA_REQUIRED = (400, "is_saved 또는 reaction 중 하나 이상 필요합니다.")
    INVALID_SOURCE = (400, "유효하지 않은 source 값입니다.")
    PREFERENCE_FIELDS_REQUIRED = (400, "genre_ids, platform_ids, tag_ids는 필수 항목입니다.")
    INVALID_STATE = (400, "유효하지 않은 state 파라미터입니다.")
    OAUTH_CALLBACK_ERROR = (400, "카카오 인증에 실패했습니다.")

    # 401 Unauthorized
    UNAUTHORIZED = (401, "인증이 필요합니다.")
    INVALID_CREDENTIALS = (401, "이메일 또는 비밀번호가 올바르지 않습니다.")
    ACCOUNT_DEACTIVATED = (401, "비활성화된 계정입니다.")
    TOKEN_EXPIRED = (401, "액세스 토큰이 만료되었습니다.")
    INVALID_REFRESH_TOKEN = (401, "유효하지 않은 리프레시 토큰입니다.")
    REFRESH_TOKEN_EXPIRED = (401, "리프레시 토큰이 만료되었습니다.")

    # 403 Forbidden
    FORBIDDEN = (403, "관리자 권한이 필요합니다.")
    ADULT_VERIFICATION_REQUIRED = (403, "성인 인증이 필요한 게임입니다.")

    # 404 Not Found
    GAME_NOT_FOUND = (404, "게임을 찾을 수 없습니다.")
    STORE_NOT_FOUND = (404, "스토어를 찾을 수 없습니다.")
    JOB_NOT_FOUND = (404, "작업을 찾을 수 없습니다.")
    INTERACTION_TYPE_NOT_FOUND = (404, "해당 interaction_type을 찾을 수 없습니다.")
    SOURCE_NOT_FOUND = (404, "해당 source를 찾을 수 없습니다.")
    USER_NOT_FOUND = (404, "사용자를 찾을 수 없습니다.")

    # 409 Conflict
    EMAIL_ALREADY_EXISTS = (409, "이미 사용 중인 이메일입니다.")
    NICKNAME_ALREADY_EXISTS = (409, "이미 사용 중인 닉네임입니다.")
    VERIFICATION_ALREADY_USED = (409, "이미 사용된 인증 정보입니다. (provider_uid 중복)")
    SYNC_ALREADY_RUNNING = (409, "이미 동기화 작업이 진행 중입니다.")
    JOB_ALREADY_RUNNING = (409, "이미 실행 중인 작업이 있습니다.")

    # 429 Too Many Requests
    TOO_MANY_REQUESTS = (429, "잠시 후 다시 시도해주세요.")

    # 500 Internal Server Error
    SERVER_ERROR = (500, "서버 오류가 발생했습니다.")
    OAUTH_ERROR = (500, "OAuth 처리 중 오류가 발생했습니다.")

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
