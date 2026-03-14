"""
수동 동기화 management command

사용 예:
    # 룩업 테이블만 동기화
    python manage.py sync_rawg --lookup-only

    # 게임 10페이지 (상세 없이, 빠른 초기 적재)
    python manage.py sync_rawg --games --max-pages 10 --no-detail

    # 전체 동기화 (룩업 → 게임)
    python manage.py sync_rawg --all

"""

import logging
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.games.services.rawg_sync import RawgSyncService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "RAWG API 데이터를 DB에 동기화합니다 (동기 실행, 개발/운영 모두 사용 가능)"

    def add_arguments(self, parser: ArgumentParser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--all",
            action="store_true",
            help="룩업 테이블 + 게임 전체 동기화",
        )
        group.add_argument(
            "--lookup-only",
            action="store_true",
            help="장르·플랫폼·태그·스토어만 동기화",
        )
        group.add_argument(
            "--games",
            action="store_true",
            help="게임만 동기화",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            default=None,
            help="게임 sync 최대 페이지 수 (미지정 시 전체)",
        )
        parser.add_argument(
            "--ordering",
            default="-added",
            choices=["-added", "-rating", "-released", "-updated"],
            help="RAWG 정렬 기준 (기본: -added)",
        )
        parser.add_argument(
            "--no-detail",
            action="store_true",
            help="게임 상세 API 호출 없이 목록만 저장 (빠른 초기 적재)",
        )

    def handle(self, *args: Any, **options: dict[str, Any]) -> None:
        service = RawgSyncService()

        try:
            if options["all"]:
                self._sync_lookup(service)
                self._sync_games(service, options)

            elif options["lookup_only"]:
                self._sync_lookup(service)

            elif options["games"]:
                self._sync_games(service, options)

        except Exception as exc:
            raise CommandError(f"sync 실패: {exc}") from exc

    def _sync_lookup(self, service: RawgSyncService) -> None:
        self.stdout.write("룩업 테이블 동기화 시작...")
        for name, fn in [
            ("genres", service.sync_genres),
            ("platforms", service.sync_platforms),
            ("tags", service.sync_tags),
            ("stores", service.sync_stores),
        ]:
            result = fn()
            self.stdout.write(f"- {name}: {result}")
        self.stdout.write(self.style.SUCCESS("룩업 테이블 동기화 완료"))

    def _sync_games(self, service: RawgSyncService, options: dict[str, Any]) -> None:
        max_pages = options.get("max_pages")
        ordering = options.get("ordering", "-added")
        fetch_detail = not options.get("no_detail", False)

        self.stdout.write(f"게임 sync 시작 (ordering={ordering}, max_pages={max_pages}, fetch_detail={fetch_detail})")
        result = service.sync_games(
            ordering=ordering,
            max_pages=max_pages,
            fetch_detail=fetch_detail,
        )
        self.stdout.write(self.style.SUCCESS(f"게임 sync 완료: {result}"))
