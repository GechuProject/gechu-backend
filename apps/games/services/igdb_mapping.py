from apps.games.services.tag_list import TagService
from apps.games.igdb.converters import extract_keyword_igdb_ids, extract_genre_igdb_ids

def map_igdb_tags(igdb_game_raw: dict) -> list[int]:
    """IGDB의 테마, 게임모드, 키워드에서 가져와서 우리 DB랑 매핑"""
    keyword_ids = extract_keyword_igdb_ids(igdb_game_raw)
    theme_ids = extract_genre_igdb_ids(igdb_game_raw)
    game_mode_ids = [m["id"] for m in igdb_game_raw.get("game_modes", [])]

    tag_ids = []
    for igdb_id in keyword_ids + theme_ids + game_mode_ids:
        db_tag_id = TagService.IGDB_ID_TO_DB_ID.get(igdb_id)
        if db_tag_id:
            tag_ids.append(db_tag_id)
    return tag_ids