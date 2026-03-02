import os
from typing import TYPE_CHECKING, Any

from celery import Celery

if TYPE_CHECKING:
    from celery import Task
else:
    Task = Any

# Django 설정 파일 지정
os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE", "config.settings.dev"))

app = Celery("config")

# settings.py에서 'CELERY_'로 시작하는 설정을 불러옴
app.config_from_object("django.conf:settings", namespace="CELERY")

# 등록된 앱(apps)에서 자동으로 tasks.py를 찾음
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self: "Task[Any, Any]") -> None:
    print(f"Request: {self.request!r}")
