from typing import Any

from rest_framework import serializers


class RawgSyncRequestSerializer(serializers.Serializer[Any]):
    full_sync = serializers.BooleanField(
        default=False,
        help_text=(
            "동기화 범위 설정\n"
            "- `false`(기본): 최근 변경분만 동기화 (ordering='-updated', max_pages=50)\n"
            "- `true`: 전체 재동기화 (ordering='-added', max_pages=None)"
        ),
    )


class TaskEnqueuedSerializer(serializers.Serializer[Any]):
    job_id = serializers.CharField(help_text="Celery 태스크 ID")
    status = serializers.CharField(help_text="항상 'pending' 반환")
    message = serializers.CharField(help_text="결과 메시지")
