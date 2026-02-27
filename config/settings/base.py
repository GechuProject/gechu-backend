from pathlib import Path
import os

# settings/ 폴더 기준: config/settings/base.py
# BASE_DIR = 프로젝트 루트 (manage.py 있는 폴더)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 공통: 앱/미들웨어/템플릿/URL/WSGI
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
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

# 공통: DB (현재 파일 그대로 유지: env 기반 + 기본값)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "gechu"),
        "USER": os.getenv("DB_USER", "gechu"),
        "PASSWORD": os.getenv("DB_PASSWORD", "gechu_password"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# 공통: 비밀번호 검증
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# 공통: 국제화/시간
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"  # 한국 기준 쓰고 싶으면 "Asia/Seoul"로 바꾸면 됨
USE_I18N = True
USE_TZ = True

# 공통: 정적 파일
STATIC_URL = "static/"

# 공통: 기본 PK 타입
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"