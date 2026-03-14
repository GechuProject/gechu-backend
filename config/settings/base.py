import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

if os.getenv("DJANGO_SETTINGS_MODULE") == "config.settings.local":
    load_dotenv(dotenv_path=BASE_DIR / "envs/.local.env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable not set")

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# Custom User Model
AUTH_USER_MODEL = "users.User"

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # 로그아웃 시 refresh 토큰 블랙리스트
    "corsheaders",
    "drf_spectacular",
    "django_filters",
]

# 추가한 도메인별 앱
CUSTOM_APPS: list[str] = [
    "apps.users.apps.UsersConfig",
    "apps.games.apps.GamesConfig",
    "apps.interactions.apps.InteractionsConfig",
    "apps.preferences.apps.PreferencesConfig",
    "apps.recommendations.apps.RecommendationsConfig",
    "apps.core",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + CUSTOM_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}

for field, value in DATABASES["default"].items():
    if field != "ENGINE" and not value:
        raise ValueError(f"Database config '{field}' is not set")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")

if not REDIS_PORT or not REDIS_HOST:
    raise ValueError("REDIS_HOST and REDIS_PORT must be set")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/1",  # Redis 서버주소
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# 장르 캐싱
GENRES_CACHE_KEY = "genres:all"  # 캐싱 키
GENRES_CACHE_TTL = 60 * 60  # 캐싱 TTL (초 단위) - 1시간

# 플랫폼 캐싱
PLATFORMS_CACHE_KEY = "platforms:all"
PLATFORMS_CACHE_TTL = 60 * 60

# Celery (RAWG 동기화, 추천 재생성 비동기 처리)
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/2"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/2"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Seoul"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# djangorestframework-simplejwt 관련 설정
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Internationalization
LANGUAGE_CODE = "ko-KR"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS (환경별 settings에서 CORS_ALLOWED_ORIGINS 설정)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# drf 관련 설정
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticatedOrReadOnly",),
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler.custom_exception_handler",
}

# drf-spectacular 관련 설정
SPECTACULAR_SETTINGS = {
    "TITLE": "게임 추천 서비스 Backend API",
    "DESCRIPTION": "사용자 취향 기반 게임 추천 웹사이트 개발을 위한 API입니다.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "dom_id": "#swagger-ui",
        "layout": "BaseLayout",
        "deepLinking": True,  # API를 클릭할때 마다 SwaggerUI의 url이 변경됩니다. (특정 API url 공유시 유용하기때문에 True설정을 사용합니다)
        "persistAuthorization": True,  # True 이면 SwaggerUI상 Authorize에 입력된 정보가 새로고침을 하더라도 초기화되지 않습니다.
        "displayOperationId": True,  # True이면 API의 urlId 값을 노출합니다. 대체로 DRF api name둘과 일치하기때문에 api를 찾을때 유용합니다.
        "filter": True,  # True 이면 Swagger UI에서 'Filter by Tag' 검색이 가능합니다
    },
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SECURITY": [
        {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    ],
}


# Social Login (OAuth2)
# GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
# GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
#
# DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
# DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
# DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")


# RAWG API
RAWG_API_KEY = os.getenv("RAWG_API_KEY")
if not RAWG_API_KEY:
    raise ValueError("RAWG_API_KEY must be set")

# Celery Beat 스케줄 (매일 새벽 3시 증분 동기화)
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "rawg-incremental-sync": {
        "task": "games.incremental_sync",
        "schedule": crontab(hour=3, minute=0),
    },
    "recommendation-process-pending-jobs": {
        "task": "apps.recommendations.tasks.process_pending_recommendation_jobs",
        "schedule": timedelta(seconds=30),
    },
}

CELERY_TASK_ACKS_LATE = True  # 실행 완료 후 ack → 워커 재시작 시 재실행 보장
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # 무거운 sync task는 1개씩


# 최근 검색 내역 Redis 보관 개수
SEARCH_HISTORY_MAX_SIZE = int(os.getenv("SEARCH_HISTORY_MAX_SIZE", "10"))
