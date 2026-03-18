from apps.games.services.tag_list import TagService


def map_igdb_tags(igdb_ids: list[int]) -> list[int]:
    igdb_to_db = TagService.get_igdb_mapping()  # 여기서 mapping 가져오기
    db_tag_ids = []
    for igdb_id in igdb_ids:
        db_id = igdb_to_db.get(igdb_id)
        if db_id:
            db_tag_ids.append(db_id)
    return db_tag_ids
