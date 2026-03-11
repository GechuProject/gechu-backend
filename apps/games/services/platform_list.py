from typing import Any, cast

from django.conf import settings
from django.core.cache import cache

from apps.games.models import Platform
from apps.games.serializers import PlatformResponseSerializer


class PlatformService:
    @staticmethod
    def get_all_platforms() -> list[dict[str, Any]]:
        """
        전체 플랫폼 조회, 캐싱 적용
        """
        # 캐시 조회
        cached_data = cache.get(settings.PLATFORMS_CACHE_KEY)
        if cached_data is not None:
            return cast(list[dict[str, Any]], cached_data)

        # DB 조회
        platforms_qs = Platform.objects.all().order_by("id")

        # 직렬화
        serializer = PlatformResponseSerializer(platforms_qs, many=True)
        serialized_data = cast(list[dict[str, Any]], serializer.data)

        # 캐시에 저장
        cache.set(settings.PLATFORMS_CACHE_KEY, serialized_data, timeout=settings.PLATFORMS_CACHE_TTL)

        return serialized_data
