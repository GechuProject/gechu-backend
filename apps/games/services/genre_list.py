from typing import Any, cast

from django.conf import settings
from django.core.cache import cache

from apps.games.models import Genre
from apps.games.serializers import GenreResponseSerializer


class GenreService:
    @staticmethod
    def get_all_genres() -> list[dict[str, Any]]:
        """
        전체 장르 조회, 캐싱 적용
        """
        # 캐시 조회
        cached_data = cache.get(settings.GENRES_CACHE_KEY)
        if cached_data is not None:  # 캐싱에서 빈 리스트도 정상 데이터
            return cast(list[dict[str, Any]], cached_data)

        # DB 조회
        genres_qs = Genre.objects.all().order_by("id")

        # 직렬화
        serializer = GenreResponseSerializer(genres_qs, many=True)
        serialized_data = cast(list[dict[str, Any]], serializer.data)

        # 캐시에 저장
        cache.set(settings.GENRES_CACHE_KEY, serialized_data, timeout=settings.GENRES_CACHE_TTL)

        return serialized_data
