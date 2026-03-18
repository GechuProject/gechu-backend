from typing import TypedDict

from django.core.paginator import Paginator
from django.db.models import Q

from apps.games.models import Tag
from apps.games.igdb.mappings import IGDB_ID_TO_SLUG


class TagListResult(TypedDict):
    results: list[Tag]


class TagService:
    # DB 조회 포함 매핑
    TAG_SLUG_TO_ID = {t.slug: t.id for t in Tag.objects.all()}
    IGDB_ID_TO_DB_ID = {igdb_id: TAG_SLUG_TO_ID[slug] for igdb_id, slug in IGDB_ID_TO_SLUG.items()}

    @staticmethod
    def get_tag_list() -> TagListResult:

        # 기본 queryset
        queryset = Tag.objects.all().order_by("name")

        return {"results": list(queryset)}
