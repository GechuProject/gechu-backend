from typing import TypedDict

from apps.games.igdb.mappings import IGDB_ID_TO_SLUG
from apps.games.models import Tag


class TagListResult(TypedDict):
    results: list[Tag]


class TagService:
    @classmethod
    def get_igdb_mapping(cls) -> dict[int, int]:
        """IGDB ID → DB Tag ID 매핑"""
        # DB에서 태그 조회
        tag_slug_to_id = {t.slug: t.id for t in Tag.objects.all()}

        # IGDB -> DB ID 매핑
        igdb_to_db_id = {
            igdb_id: tag_slug_to_id[slug] for igdb_id, slug in IGDB_ID_TO_SLUG.items() if slug in tag_slug_to_id
        }
        return igdb_to_db_id

    @staticmethod
    def get_tag_list() -> TagListResult:

        # 기본 queryset
        queryset = Tag.objects.all().order_by("name")

        return {"results": list(queryset)}
