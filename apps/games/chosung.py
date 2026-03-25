"""
한글 초성 추출 유틸리티

저장 및 검색 모두 get_chosung_normalized() 사용 (양쪽 동일해야 매칭됨)
영어/숫자/특수문자는 그대로 유지
name_ko 없으면 빈 문자열 반환 (영어 name은 chosung 저장 안 함)
"""

CHOSUNG_LIST = [
    "ㄱ",
    "ㄲ",
    "ㄴ",
    "ㄷ",
    "ㄸ",
    "ㄹ",
    "ㅁ",
    "ㅂ",
    "ㅃ",
    "ㅅ",
    "ㅆ",
    "ㅇ",
    "ㅈ",
    "ㅉ",
    "ㅊ",
    "ㅋ",
    "ㅌ",
    "ㅍ",
    "ㅎ",
]


def get_chosung(text: str) -> str:
    """한글 → 초성 추출. 비한글 문자는 그대로 유지"""
    result = []
    for char in text:
        if "가" <= char <= "힣":
            code = ord(char) - ord("가")
            result.append(CHOSUNG_LIST[code // 588])
        else:
            result.append(char)
    return "".join(result)


def get_chosung_normalized(text: str) -> str:
    """공백 제거 + 초성 추출. DB/캐시 저장 및 검색 모두 이 함수 사용"""
    if not text:
        return ""
    return get_chosung(text).replace(" ", "")
