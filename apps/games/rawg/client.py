"""
RawgClient: RAWG Video Games Database API HTTP Wrapper

설계 원칙:
- _get(): 단건 GET, 상태코드별 예외 변환
- _paginate(): 페이지(list) 단위 제너레이터. rate limit 발생 시 Retry-After 대기 후 1회 재시도
- iter_*: 페이지네이션 공개 인터페이스 → Generator[list[dict], None, None]
- get_*: 단건 조회 공개 인터페이스

Rate Limit 처리 흐름:
    _paginate() → RawgRateLimitError 캐치
    → response의 Retry-After 헤더값만큼 sleep
    → 해당 페이지 1회 재시도
    → 재시도도 실패하면 RawgRateLimitError 그대로 raise
    → Celery 태스크가 countdown으로 재스케줄

주의: 429는 _build_session()의 status_forcelist에 넣지 않음
      urllib3 Retry는 Retry-After를 무시하고 재시도하기 때문
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from typing import Any, cast
from urllib.parse import urljoin

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import RawgNotFoundError, RawgRateLimitError, RawgServerError

logger = logging.getLogger(__name__)

# RAWG free tier: 5 req/s, page_size 최대 40
_PAGE_SIZE = 40
# 무한루프 방어: 페이지 수 상한
_MAX_PAGES = 1_000
# 단일 요청 타임아웃 (초)
_REQUEST_TIMEOUT = 30
# 페이지 간 sleep 간격 (5 req/s 유지)
_PAGE_INTERVAL = 0.25


def _build_session() -> requests.Session:
    """
    Retry 전략이 적용된 requests.Session 반환

    재시도 대상:
        - 상태코드: 500, 502, 503, 504 (429는 제외 - Retry-After 직접 처리)
        - 메서드: GET만
        - 최대 3회, 지수 백오프 (1s → 2s → 4s)
    """
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],  # 429 제외
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class RawgClient:
    """
    RAWG API Wrapper.

    사용 예:
        client = RawgClient()

        # 페이지 단위 순회 (서비스 레이어에서 bulk_create 용)
        for page_results in client.iter_games(ordering="-added"):
            process_page(page_results)  # page_results: list[dict]

        # 단건 조회
        detail = client.get_game_detail(3498)
    """

    BASE_URL = "https://api.rawg.io/api/"

    def __init__(self) -> None:
        self._api_key: str = settings.RAWG_API_KEY  # type: ignore
        assert self._api_key, "RAWG_API_KEY must be set"
        self._session: requests.Session = _build_session()

    # 내부 헬퍼 함수

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        단건 GET 요청

        Args:
            path: BASE_URL 기준 상대 경로 (예: "games/3498")
            params: 쿼리 파라미터 (key 자동 포함)

        Returns:
            JSON 응답 dict

        Raises:
            RawgRateLimitError: HTTP 429 (retry_after 속성에 Retry-After 값 포함)
            RawgNotFoundError:  HTTP 404
            RawgServerError:    HTTP 5xx
        """
        url = urljoin(self.BASE_URL, path)
        merged_params = {"key": self._api_key, **(params or {})}

        resp = self._session.get(url, params=merged_params, timeout=_REQUEST_TIMEOUT)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 60))
            raise RawgRateLimitError(retry_after=retry_after)
        if resp.status_code == 404:
            raise RawgNotFoundError(f"Not found: {url}")
        if resp.status_code >= 500:
            raise RawgServerError(
                f"RAWG 서버 오류 {resp.status_code}: {url}",
                status_code=resp.status_code,
            )

        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def _paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Generator[list[dict[str, Any]]]:
        """
        RAWG 페이지네이션 제너레이터

        페이지(list[dict]) 단위로 yield → 서비스 레이어에서 bulk_create 가능

        - results 없거나 next 없으면 종료
        - _MAX_PAGES 초과 시 경고 로그 후 중단
        - 429 발생 시 Retry-After만큼 대기 후 해당 페이지 1회 재시도
        - 페이지 간 _PAGE_INTERVAL sleep
        """
        page = 1
        merged_params = {
            "page_size": _PAGE_SIZE,
            "page": page,
            **(params or {}),
        }

        while True:
            if page > _MAX_PAGES:
                logger.warning("_MAX_PAGES(%d) 초과, 순회 중단", _MAX_PAGES)
                break

            try:
                data = self._get(path, merged_params)
            except RawgRateLimitError as e:
                logger.warning("Rate limit, %ds 대기 후 재시도 (page=%d)", e.retry_after, page)
                time.sleep(e.retry_after)
                data = self._get(path, merged_params)  # 1회 재시도, 실패 시 그대로 raise

            results: list[dict[str, Any]] = data.get("results", [])
            if not results:
                break

            yield results  # 페이지 단위 yield (list[dict])

            if not data.get("next"):
                break

            page += 1
            merged_params["page"] = page
            time.sleep(_PAGE_INTERVAL)

    # 공개 인터페이스 --------------------------------------------------------
    def iter_games(self, **params: Any) -> Generator[list[dict[str, Any]]]:
        """
        GET /games 페이지 순회
        ordering 등 RAWG 쿼리 파라미터 전달 가능

        예: client.iter_games(ordering="-added")
        """
        yield from self._paginate("games", params)

    def get_game_detail(self, rawg_id: int) -> dict[str, Any]:
        """GET /games/{id} - description, website, stores 등 포함된 상세 정보"""
        return self._get(f"games/{rawg_id}")

    def get_game_screenshots(self, rawg_id: int) -> list[dict[str, Any]]:
        """
        GET /games/{id}/screenshots - 전체 목록 반환
        페이지네이션 처리하여 모든 스크린샷 수집
        """
        results: list[dict[str, Any]] = []
        for page in self._paginate(f"games/{rawg_id}/screenshots"):
            results.extend(page)
        return results

    def get_game_trailers(self, rawg_id: int) -> list[dict[str, Any]]:
        """
        GET /games/{id}/movies - 전체 목록 반환
        페이지네이션 처리하여 모든 트레일러 수집
        """
        results: list[dict[str, Any]] = []
        for page in self._paginate(f"games/{rawg_id}/movies"):
            results.extend(page)
        return results

    def iter_genres(self) -> Generator[list[dict[str, Any]]]:
        """GET /genres 페이지 순회"""
        yield from self._paginate("genres")

    def iter_platforms(self) -> Generator[list[dict[str, Any]]]:
        """GET /platforms 페이지 순회"""
        yield from self._paginate("platforms")

    def iter_tags(self) -> Generator[list[dict[str, Any]]]:
        """GET /tags 페이지 순회"""
        yield from self._paginate("tags")

    def iter_stores(self) -> Generator[list[dict[str, Any]]]:
        """GET /stores 페이지 순회"""
        yield from self._paginate("stores")
