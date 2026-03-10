from typing import Any, cast

from django.core.cache import cache

from apps.games.models import Genre
from apps.games.serializers import GenreResponseSerializer

# 캐싱 키
GENRES_CACHE_KEY = "genres:all"
# 캐싱 TTL (초 단위) - 예: 1시간
GENRES_CACHE_TTL = 60 * 60


class GenreService:
    @staticmethod
    def get_all_genres() -> list[dict[str, Any]]:
        """
        전체 장르 조회, 캐싱 적용
        """
        # 캐시 조회
        cached_data = cache.get(GENRES_CACHE_KEY)
        if cached_data is not None:  # 캐싱에서 빈 리스트도 정상 데이터
            return cast(list[dict[str, Any]], cached_data)

        # DB에서 조회
        genres_qs = Genre.objects.all().order_by("id")

        # 직렬화
        serializer = GenreResponseSerializer(genres_qs, many=True)
        serialized_data = cast(list[dict[str, Any]], serializer.data)

        # 캐시에 저장
        cache.set(GENRES_CACHE_KEY, serialized_data, timeout=GENRES_CACHE_TTL)

        return serialized_data
