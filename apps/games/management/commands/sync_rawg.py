"""
수동 동기화 management command

사용 예:
    python manage.py sync_rawg --all
    python manage.py sync_rawg --lookup-only
    python manage.py sync_rawg --games --max-pages 10 --no-detail
    python manage.py sync_rawg --game-id 3498
"""

# import logging
#
# from django.core.management.base import BaseCommand
#
# logger = logging.getLogger(__name__)
#
#
# class Command(BaseCommand):
#     help = "RAWG API 데이터를 DB에 동기화합니다"


# TODO: add_arguments - --all/--lookup-only/--games/--game-id (mutually exclusive)
#                       --max-pages / --ordering (choices 제한) / --no-detail
# def add_arguments(self, parser: ArgumentParser) -> None:
#     group = parser.add_mutually_exclusive_group(required=True)
#     group.add_argument("--all", action="store_true", help="전체 데이터 동기화")
#     group.add_argument("--lookup-only", action="store_true", help="장르/플랫폼/태그/스토어 조회만")
#     group.add_argument("--games", action="store_true", help="게임 데이터만 동기화")
#     group.add_argument("--game-id", type=int, help="특정 게임 ID만 동기화")


# TODO: handle - 옵션별 분기, CommandError로 예외 래핑

# TODO: _sync_lookup(service) - 장르/플랫폼/태그/스토어 순서대로, 결과 stdout 출력
# TODO: _sync_games(service, options) - max_pages/ordering/fetch_detail 추출 후 서비스 호출
