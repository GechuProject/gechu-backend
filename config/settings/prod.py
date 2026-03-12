import json
import os
import re
from datetime import timedelta

from config.settings.base import *

DEBUG = False

RAW_ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "")
if not RAW_ALLOWED_HOSTS:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set")

ALLOWED_HOSTS = [h.strip() for h in re.split(r"[,\s]+", RAW_ALLOWED_HOSTS) if h.strip()]

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# cors & csrf settings
raw_cors = os.getenv("CORS_ALLOWED_ORIGINS", "")

try:
    if raw_cors.startswith("["):
        CORS_ALLOWED_ORIGINS = json.loads(raw_cors)
    else:
        CORS_ALLOWED_ORIGINS = [origin.strip() for origin in re.split(r"[,\s]+", raw_cors) if origin.strip()]

    CORS_ALLOWED_ORIGINS = [origin.strip().strip("'").strip('"').rstrip("/") for origin in CORS_ALLOWED_ORIGINS]

except (json.JSONDecodeError, TypeError):
    CORS_ALLOWED_ORIGINS = []

CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# jwt access token lifetime
SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(minutes=60)

# logging settings
LOG_ROOT = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_ROOT):
    os.makedirs(LOG_ROOT)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_ROOT, "django.log"),
            "formatter": "verbose",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 10,
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file", "mail_admins"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# CloudFront 프록시 설정
# CloudFront가 보낸 X-Forwarded-Proto: https 헤더를 장고가 HTTPS로 인식하게 함
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# 전달받은 Host 헤더를 신뢰하여 ALLOWED_HOSTS와 대조 및 URL 생성에 사용
USE_X_FORWARDED_HOST = True

# HTTPS security
# True일 경우 모든 HTTP 요청을 HTTPS로 강제 리다이렉트
SECURE_SSL_REDIRECT = False

# 세션 쿠키를 HTTPS 연결에서만 전송하도록 설정
SESSION_COOKIE_SECURE = True

# CSRF 쿠키를 HTTPS 연결에서만 전송하도록 설정: HTTP 환경에서 CSRF 토큰이 노출되는 것을 방지
CSRF_COOKIE_SECURE = True
