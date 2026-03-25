"""
위키데이터에서 한국어 게임 이름 일괄 업데이트

사용법:
    python manage.py fill_name_ko
    python manage.py fill_name_ko --overwrite
    python manage.py fill_name_ko --chunk-size 50
    python manage.py fill_name_ko --igdb-ids 1942,1234
"""

from __future__ import annotations

import time
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django_redis import get_redis_connection

from apps.games.wikidata.client import _KEY_PREFIX, fetch_and_save_bulk


class Command(BaseCommand):
    help = "위키데이터에서 한국어 게임 이름을 일괄 업데이트합니다"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--overwrite", action="store_true", help="기존 데이터 덮어쓰기")
        parser.add_argument("--chunk-size", type=int, default=50)
        parser.add_argument("--igdb-ids", type=str, help="쉼표 구분 IGDB ID 목록")

    def handle(self, *args: Any, **options: Any) -> None:
        r = get_redis_connection("default")

        if options["igdb_ids"]:
            igdb_ids = [int(x.strip()) for x in options["igdb_ids"].split(",") if x.strip()]
            igdb_id_to_slug = self._fetch_slugs_from_igdb(igdb_ids)
        elif options["overwrite"]:
            igdb_id_to_slug = self._collect_all_from_igdb_cache(r)
        else:
            igdb_id_to_slug = self._collect_pending_from_redis(r)

        total = len(igdb_id_to_slug)
        self.stdout.write(f"대상 게임: {total}개")

        if not total:
            self.stdout.write("처리할 게임이 없습니다.")
            return

        chunk_size = options["chunk_size"]
        updated = 0
        items = list(igdb_id_to_slug.items())

        for i in range(0, total, chunk_size):
            chunk = dict(items[i : i + chunk_size])
            results = fetch_and_save_bulk(chunk)
            hit = sum(1 for v in results.values() if v)
            updated += hit
            self.stdout.write(f"  {min(i + chunk_size, total)}/{total} 처리 (히트: {hit}개)")
            if i + chunk_size < total:
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"완료: {updated}/{total}개 한국어 이름 저장"))

    def _fetch_slugs_from_igdb(self, igdb_ids: list[int]) -> dict[int, str]:
        """IGDB API에서 slug 조회"""
        from apps.games.igdb.client import get_igdb_client

        client = get_igdb_client()
        results = client.get_games_by_ids(igdb_ids)
        return {game["id"]: game["slug"] for game in results if game.get("slug")}

    def _collect_pending_from_redis(self, r: Any) -> dict[int, str]:
        """fetched_at 없는 pending 키에서 slug 수집"""
        igdb_id_to_slug: dict[int, str] = {}
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{_KEY_PREFIX}*", count=200)
            for key in keys:
                data = r.hgetall(key)
                if not data.get(b"fetched_at"):
                    slug_raw = data.get(b"slug")
                    if not slug_raw:
                        continue
                    try:
                        igdb_id = int(key.decode().replace(_KEY_PREFIX, ""))
                        igdb_id_to_slug[igdb_id] = slug_raw.decode()
                    except (ValueError, AttributeError):
                        pass
            if cursor == 0:
                break
        return igdb_id_to_slug

    def _collect_all_from_igdb_cache(self, r: Any) -> dict[int, str]:
        """IGDB 게임 캐시(*igdb:game:*, *igdb:search:*)에서 id→slug 수집"""
        import json

        igdb_id_to_slug: dict[int, str] = {}

        # igdb:game:* 캐시에서 수집 (django-redis 프리픽스 포함)
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match="*igdb:game:*", count=200)
            for key in keys:
                data = r.get(key)
                if data:
                    try:
                        game = json.loads(data)
                        igdb_id = game.get("id")
                        slug = game.get("slug")
                        if igdb_id and slug:
                            igdb_id_to_slug[int(igdb_id)] = slug
                    except (ValueError, KeyError, TypeError):
                        pass
            if cursor == 0:
                break

        # igdb:search:* 캐시에서도 수집 (검색 결과 캐시)
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match="*igdb:search:*", count=200)
            for key in keys:
                data = r.get(key)
                if data:
                    try:
                        games = json.loads(data)
                        if isinstance(games, list):
                            for game in games:
                                igdb_id = game.get("id")
                                slug = game.get("slug")
                                if igdb_id and slug:
                                    igdb_id_to_slug[int(igdb_id)] = slug
                    except (ValueError, KeyError, TypeError):
                        pass
            if cursor == 0:
                break

        return igdb_id_to_slug
