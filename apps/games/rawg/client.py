# RAWG API 호출 담당
"""
RawgClient: RAWG Video Games Database API HTTP Wrapper
"""

from __future__ import annotations

import logging
import time
from typing import Any, Generator
from urllib.parse import urljoin

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import RawgNotFoundError, RawgRateLimitError, RawgServerError

logger = logging.getLogger(__name__)

# # TODO: _PAGE_SIZE, _MAX_PAGES, _REQUEST_TIMEOUT, _PAGE_INTERVAL 상수 정의
_PAGE_SIZE = 50            # 한 페이지당 가져올 아이템 수
_MAX_PAGES = 60            # 최대 페이지 수
_REQUEST_TIMEOUT = 10      # HTTP 요청 타임아웃(초)
_PAGE_INTERVAL = 0.5       # 페이지 요청 간 딜레이(초, rate limit 방지) 총 30초

# # TODO: _build_session() → Retry 전략 적용된 Session 반환
# 네트워크 오류, 서버 오류 발생 -> 요청 자동 재시도
'''
# 코드 의미
429	Rate Limit 초과
500	서버 에러
502	Bad Gateway
503	Service Unavailable
504	Gateway Timeout
'''
def _build_session() -> requests.Session:
    retry = Retry(
        total=3,                                    # 최대 3번 재시도
        backoff_factor=0.5,                         # 재시도 사이의 대기 시간
        status_forcelist=[429, 500, 502, 503, 504], # retry되는 상태코드
        raise_on_status=False,
        allowed_methods=["GET"],                    # GET만 retry

    )

    # Retry 정책 적용
    adapter = HTTPAdapter(max_retries=retry)

    # Session 생성
    session = requests.Session()    # Session -> 연결 재사용(API 호출 성능 향상)

    # 모든 요청에 Retry 정책 적용
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session

# _build_session() 호출
class RawgClient:

    BASE_URL = "https://api.rawg.io/api/"

    def __init__(self) -> None:
        self._api_key: str = settings.RAWG_API_KEY
        self._session: requests.Session = _build_session()
#
#   # TODO: _get(path, params) → 단건 GET, 상태코드별 예외 처리
    # GET 요청 -> 상태 코드 검사 -> exception 발생 -> json 반환
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = urljoin(self.BASE_URL, path)

        params = params or {}
        params["key"] = self._api_key   # 모든 api 호출에 자동으로 내 key 추가

        response = self._session.get(
            url,
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )

        status = response.status_code

        if status == 404:
            raise RawgNotFoundError("RAWG resource not found")

        if status == 429:
            raise RawgRateLimitError("RAWG rate limit exceeded")

        if 500 <= status < 600:
            raise RawgServerError(f"RAWG server error: {status}")

        response.raise_for_status()

        return response.json()

#     # TODO: _paginate(path, params) → 페이지네이션 제너레이터, rate limit 재시도 포함
#
#     # TODO: iter_games / get_game_detail / get_game_screenshots / get_game_trailers
#     #       iter_genres / iter_platforms / iter_tags / iter_stores
