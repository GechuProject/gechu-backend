"""
name_ko resolve 로직

우선순위:
    1. 캐시된 name_ko (Redis Hash, fetched_at 있음)
    2. parent_game의 name_ko + 에디션 suffix
    3. IGDB alternative_names (즉시 사용 가능)
    4. "" → 호출부에서 영어 name fallback

캐시 미스(pending) 시 Celery enqueue
API 요청 중 외부 API 절대 호출하지 않음
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.games.igdb.converters import extract_korean_from_alt_names
from apps.games.wikidata.client import (
    acquire_enqueue_lock,
    get_failed_count,
    get_name_ko_from_cache,
)

_MAX_FAILED = 3

# 에디션 키워드 로드
_KEYWORDS_FILE = Path(__file__).parent / "edition_keywords.json"
with open(_KEYWORDS_FILE, encoding="utf-8") as f:
    _EDITION_KEYWORDS = json.load(f)["keywords"]


def resolve_name_ko(igdb_id: int, raw: dict[str, Any]) -> str:
    """
    캐시 히트 시 즉시 반환 (suffix 있으면 추가)
    캐시 미스(pending) 시:
      1. parent_game 있으면 부모 게임 한국어 + 에디션 suffix
      2. parent_game 없으면 게임 이름에서 추론 시도
      3. alternative_names fallback
      4. Celery enqueue
    실패 횟수 초과 시 enqueue 안 함
    """
    name_ko = get_name_ko_from_cache(igdb_id)
    if name_ko:
        # 캐시에 있어도 에디션 suffix 추가
        edition_suffix = _extract_edition_suffix(raw.get("name", ""))
        if edition_suffix:
            return f"{name_ko} - {edition_suffix}"
        return name_ko

    # parent_game 활용
    parent_game_id = raw.get("parent_game")

    # parent_game이 없거나, 있어도 캐시에 없으면 게임 이름에서 추론 시도
    if parent_game_id:
        parent_name_ko = get_name_ko_from_cache(parent_game_id)
        if parent_name_ko:
            edition_suffix = _extract_edition_suffix(raw.get("name", ""))
            if edition_suffix:
                return f"{parent_name_ko} - {edition_suffix}"
            return parent_name_ko

    # parent_game이 없거나 캐시에 없으면 추론 시도
    if not parent_game_id or not get_name_ko_from_cache(parent_game_id):
        inferred_parent_id = _infer_parent_game_id(raw.get("name", ""))
        if inferred_parent_id:
            parent_name_ko = get_name_ko_from_cache(inferred_parent_id)
            if parent_name_ko:
                edition_suffix = _extract_edition_suffix(raw.get("name", ""))
                if edition_suffix:
                    return f"{parent_name_ko} - {edition_suffix}"
                return parent_name_ko

    slug = raw.get("slug", "")
    if slug:
        _maybe_enqueue(igdb_id, slug)

    return extract_korean_from_alt_names(raw) or ""


def _extract_edition_suffix(full_name: str) -> str:
    """
    게임 이름에서 에디션/모드 suffix 추출
    예: "The Legend of Zelda: Tears of the Kingdom - Nintendo Switch 2 Edition"
        -> "Nintendo Switch 2 Edition"
        "The Legend of Zelda: Tears of the Kingdom Randomizer"
        -> "Randomizer"
        "Assassin's Creed II: Deluxe Edition"
        -> "Deluxe Edition"

    키워드는 edition_keywords.json에서 로드

    단일 단어 suffix는 명확한 에디션 키워드와 함께 있을 때만 인정:
    - "Ultimate Edition" ✓
    - "Ultimate Fighting" ✗
    """
    # 명확한 에디션 표시 키워드 (단일 단어와 함께 있어야 함)
    STRONG_KEYWORDS = {
        "edition",
        "collection",
        "bundle",
        "pack",
        "remastered",
        "remaster",
        "remake",
        "redux",
        "dlc",
        "expansion",
        "goty",
        "version",
        "ver",
    }

    # 패턴 1: " - suffix" (가장 명확, 최우선)
    match = re.search(r" - (.+)$", full_name)
    if match:
        suffix = match.group(1).strip()
        if any(keyword.lower() in suffix.lower() for keyword in _EDITION_KEYWORDS):
            return suffix

    # 패턴 2: ": suffix" (콜론으로 구분, 마지막 콜론 이후)
    # 예: "Assassin's Creed II: Deluxe Edition" -> "Deluxe Edition"
    if ": " in full_name:
        parts = full_name.split(": ")
        last_part = parts[-1].strip()
        last_part_words = last_part.split()

        # 마지막 부분이 짧고 키워드를 포함하는 경우만 (최대 4단어)
        if len(last_part_words) <= 4:
            # 단일 단어인 경우: 명확한 에디션 키워드만 허용
            if len(last_part_words) == 1:
                if any(keyword.lower() == last_part.lower() for keyword in STRONG_KEYWORDS):
                    return last_part
            # 2단어 이상: 명확한 키워드가 포함되어 있으면 허용
            else:
                if any(keyword.lower() in last_part.lower() for keyword in STRONG_KEYWORDS):
                    return last_part

    # 패턴 3: 마지막 단어가 단독 키워드인 경우 (공백으로 구분)
    # 예: "Game Name Randomizer" -> "Randomizer"
    # 주의: 명확한 에디션 키워드만 허용
    words = full_name.split()
    if len(words) > 1:
        last_word = words[-1]
        # 명확한 에디션 키워드만 단독으로 허용
        if any(keyword.lower() == last_word.lower() for keyword in STRONG_KEYWORDS):
            return last_word

        # 또는 "Randomizer", "Mod" 같은 특수 키워드
        SPECIAL_SINGLE_KEYWORDS = {"randomizer", "mod"}
        if last_word.lower() in SPECIAL_SINGLE_KEYWORDS:
            # 바로 앞 단어가 키워드가 아닌 경우만
            if len(words) >= 2:
                second_last = words[-2]
                if not any(keyword.lower() == second_last.lower() for keyword in _EDITION_KEYWORDS):
                    return last_word

    return ""


@lru_cache(maxsize=1024)
def _infer_parent_game_id(game_name: str) -> int | None:
    """
    게임 이름에서 suffix를 제거하고 원본 게임 ID를 추론
    예: "The Legend of Zelda: Tears of the Kingdom - Collector's Edition"
        -> "The Legend of Zelda: Tears of the Kingdom" 검색
        -> 119388 반환

    결과는 LRU 캐시에 저장되어 같은 게임 이름으로 반복 조회 시 IGDB API 호출 안 함
    """
    suffix = _extract_edition_suffix(game_name)
    if not suffix:
        return None

    # suffix 제거하여 원본 게임 이름 추출
    base_name = game_name
    if f" - {suffix}" in base_name:
        base_name = base_name.replace(f" - {suffix}", "").strip()
    elif f": {suffix}" in base_name:
        base_name = base_name.replace(f": {suffix}", "").strip()
    elif base_name.endswith(f" {suffix}"):
        base_name = base_name[: -len(f" {suffix}")].strip()

    if not base_name or base_name == game_name:
        return None

    # IGDB에서 원본 게임 검색
    try:
        from apps.games.igdb.client import get_igdb_client

        client = get_igdb_client()
        results = client.search_games(query=base_name, limit=5)

        # 정확히 일치하는 게임 찾기
        for game in results:
            if game.get("name", "").lower() == base_name.lower():
                return int(game["id"])

        # 정확히 일치하는 게임이 없으면 첫 번째 결과 반환
        if results:
            return int(results[0]["id"])
    except Exception:
        # IGDB 조회 실패 시 None 반환
        pass

    return None


def _maybe_enqueue(igdb_id: int, slug: str) -> None:
    if get_failed_count(igdb_id) >= _MAX_FAILED:
        return
    if not acquire_enqueue_lock(igdb_id):
        return

    from apps.games.tasks import fetch_name_ko_task

    fetch_name_ko_task.delay(igdb_id, slug)
