from rest_framework.pagination import PageNumberPagination


class GamePagination(PageNumberPagination):
    page_size = 20  # 기본 20개
    page_size_query_param = "page_size"
    max_page_size = 100  # 최대 100개 제한
