from apps.games.models import Game
from apps.games.igdb.mapping import map_igdb_tags

def sync_game_tags(game: Game, igdb_game_raw: dict, replace: bool = True) -> None:
    """
    IGDB raw 데이터를 기반으로 게임의 태그를 DB와 연결
    :param game: Game 모델 인스턴스
    :param igdb_game_raw: IGDB에서 가져온 게임 raw 데이터
    :param replace: True면 기존 태그 제거 후 새로 연결, False면 추가만
    """
    tag_ids = map_igdb_tags(igdb_game_raw)

    if replace:
        game.tags.set(tag_ids)
    else:
        game.tags.add(*tag_ids)