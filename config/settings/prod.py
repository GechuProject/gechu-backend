import json
import os
import re

import sentry_sdk
import timedelta

from config.settings.base import *

DEBUG = False

RAW_ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "")
if not RAW_ALLOWED_HOSTS:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set")

ALLOWED_HOSTS = [h.strip() for h in re.split(r"[,\s]+", RAW_ALLOWED_HOSTS) if h.strip()]

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

# sentry logging settings
# SENTRY_DSN = os.getenv("SENTRY_DSN")
# if not SENTRY_DSN:
#     raise ValueError("SENTRY_DSN must be set. For Error Logging")
# sentry_sdk.init(
#     dsn=SENTRY_DSN,
#     traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", 1)),
#     profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", 1)),
# )

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
