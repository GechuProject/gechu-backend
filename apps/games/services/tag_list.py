from typing import TypedDict

from django.core.paginator import Paginator
from django.db.models import Q

from apps.games.models import Tag


class TagListResult(TypedDict):
    count: int
    results: list[Tag]


class TagService:
    @staticmethod
    def get_tag_list(search: str | None, page: int, page_size: int) -> TagListResult:

        # 기본 queryset
        queryset = Tag.objects.all()

        # 검색 필터
        if search:
            search = search.strip()

            queryset = queryset.filter(Q(name__icontains=search) | Q(slug__icontains=search))

        # 정렬
        queryset = queryset.order_by("name")

        # 페이지네이션
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        return {"count": paginator.count, "results": list(page_obj.object_list)}
