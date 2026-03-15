"""
수동 동기화 management command

사용 예:
    # 룩업 테이블만 동기화
    python manage.py sync_igdb --lookup-only

    # 게임 10페이지
    python manage.py sync_igdb --games --max-pages 10

    # 전체 동기화 (룩업 → 게임)
    python manage.py sync_igdb --all
"""

from __future__ import annotations

import logging
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.games.igdb.service import IgdbSyncService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "IGDB API 데이터를 DB에 동기화합니다 (동기 실행, 개발/운영 모두 사용 가능)"

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
            help="장르·플랫폼·키워드(태그)만 동기화",
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

    def handle(self, *args: Any, **options: Any) -> None:
        service = IgdbSyncService()
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

    def _sync_lookup(self, service: IgdbSyncService) -> None:
        self.stdout.write("룩업 테이블 동기화 시작...")
        for name, fn in [
            ("genres", service.sync_genres),
            ("platforms", service.sync_platforms),
            ("tags(keywords)", service.sync_tags),
        ]:
            result = fn()
            self.stdout.write(f"  - {name}: {result}")
        self.stdout.write(self.style.SUCCESS("룩업 테이블 동기화 완료"))

    def _sync_games(self, service: IgdbSyncService, options: dict[str, Any]) -> None:
        max_pages = options.get("max_pages")
        self.stdout.write(f"게임 sync 시작 (max_pages={max_pages})")
        result = service.sync_games(max_pages=max_pages)
        self.stdout.write(self.style.SUCCESS(f"게임 sync 완료: {result}"))
