from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework.pagination import PageNumberPagination


class Pagination(PageNumberPagination):
    page_size = 20  # 기본 20개
    page_size_query_param = "page_size"
    max_page_size = 100  # 최대 100개 제한


PAGINATION_PARAMS = [
    OpenApiParameter(name="page", type=OpenApiTypes.INT, location="query", description="조회할 페이지 번호"),
    OpenApiParameter(
        name="page_size", type=OpenApiTypes.INT, location="query", description="페이지당 결과 수 (최대: 100)"
    ),
]