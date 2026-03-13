import secrets

from apps.users.models.user import User

NICKNAME_PREFIXES = [
    "빠른",
    "게임하는",
    "최고의",
    "강아지좋아하는",
    "고양이좋아하는",
    "슬픈",
    "게임금지당한",
    "행복한",
    "이세계의",
    "한방좋아하는",
    "빨간색",
    "검은색",
    "파란색",
    "귀여운",
    "깜찍한",
    "적응하는",
    "최상급",
    "까칠한",
    "쿨한",
    "과일좋아하는",
    "잘먹는",
    "하얀색",
    "키작은",
    "키큰",
    "멋있는",
    "잘생긴",
]

NICKNAME_SUFFIXES = [
    "고양이",
    "강아지",
    "돼지",
    "소",
    "토끼",
    "양",
    "곰",
    "사자",
    "호랑이",
    "늑대",
    "여우",
    "사슴",
    "코끼리",
    "기린",
    "하마",
    "말",
    "당나귀",
    "캥거루",
    "코알라",
    "팬더",
    "몽구스",
    "고슴도치",
    "너구리",
    "두더지",
    "멧돼지",
    "치타",
    "표범",
    "침팬지",
    "햄스터",
    "돌고래",
    "바다사자",
    "바다코끼리",
    "하프물범",
    "가물치",
    "가리비",
    "상어",
    "고래",
]


def generate_unique_nickname() -> str:
    while True:
        prefix = NICKNAME_PREFIXES[secrets.randbelow(len(NICKNAME_PREFIXES))]
        suffix = NICKNAME_SUFFIXES[secrets.randbelow(len(NICKNAME_SUFFIXES))]
        nickname = f"{prefix}{suffix}"

        if not User.objects.filter(nickname=nickname).exists():
            return nickname
