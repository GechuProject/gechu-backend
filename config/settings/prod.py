from .base import *
import os

DEBUG = False

# 운영은 반드시 환경변수로만 받기(없으면 바로 터지게)
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# 예: "api.gechu.com,www.gechu.com"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

# 기본 보안 세팅(최소)
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True