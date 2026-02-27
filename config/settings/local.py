from .base import *
import os

DEBUG = True

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]