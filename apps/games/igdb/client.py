"""
IgdbClient: IGDB Video Games Database API HTTP Wrapper

설계 원칙:
- Twitch OAuth2 Bearer 토큰 인증 (60일 유효, 만료 시 자동 재발급)
- _post(): 단건 POST 요청, 상태코드별 예외 변환
- _paginate(): offset 기반 페이지네이션 제너레이터
- iter_*: 페이지네이션 공개 인터페이스 → Generator[list[dict], None, None]
- get_*: 단건/전체 조회 공개 인터페이스

인증 흐름:
    IgdbClient() 생성 시 → _fetch_token() 호출
    → POST https://id.twitch.tv/oauth2/token
    → access_token 보관
    → 401 발생 시 → 토큰 재발급 후 1회 재시도

Rate Limit:
    IGDB 무료 티어: 4 req/s
    _paginate()에서 요청 간 _REQUEST_INTERVAL sleep

이미지 URL 조합:
    https://images.igdb.com/igdb/image/upload/t_{size}/{image_id}.jpg
    size: cover_big, screenshot_med, screenshot_big 등
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from typing import Any, cast

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    IgdbAuthError,
    IgdbNotFoundError,
    IgdbRateLimitError,
    IgdbServerError,
)

logger = logging.getLogger(__name__)

# IGDB 무료 티어: 4 req/s
_PAGE_SIZE = 500  # IGDB 최대 500
_MAX_PAGES = 500  # 무한루프 방어
_REQUEST_INTERVAL = 0.25  # 4 req/s 유지
_REQUEST_TIMEOUT = 30

# 이미지 베이스 URL
_IMAGE_BASE_URL = "https://images.igdb.com/igdb/image/upload"

# Twitch OAuth2 토큰 엔드포인트
_TOKEN_URL = "https://id.twitch.tv/oauth2/token"


def _build_session() -> requests.Session:
    """5xx에 대해 최대 3회 재시도하는 Session 반환 (429 제외)"""
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_image_url(image_id: str, size: str = "cover_big") -> str:
    """IGDB image_id → 이미지 URL 변환"""
    return f"{_IMAGE_BASE_URL}/t_{size}/{image_id}.jpg"


class IgdbClient:
    """
    IGDB API Wrapper.

    사용 예:
        client = IgdbClient()

        for page in client.iter_games():
            process_page(page)

        detail = client.get_game(1942)
    """

    BASE_URL = "https://api.igdb.com/v4"

    def __init__(self) -> None:
        self._client_id: str = settings.IGDB_CLIENT_ID  # type: ignore
        self._client_secret: str = settings.IGDB_CLIENT_SECRET  # type: ignore
        assert self._client_id, "IGDB_CLIENT_ID must be set"
        assert self._client_secret, "IGDB_CLIENT_SECRET must be set"
        self._session = _build_session()
        self._access_token: str = self._fetch_token()

    # 인증 --------------------------------------------------------------

    def _fetch_token(self) -> str:
        """Twitch OAuth2 Client Credentials 토큰 발급"""
        resp = self._session.post(
            _TOKEN_URL,
            params={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return cast(str, resp.json()["access_token"])

    def _headers(self) -> dict[str, str]:
        return {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    # 내부 헬퍼 ---------------------------------------------------------
    def _post(self, endpoint: str, query: str) -> list[dict[str, Any]]:
        """
        단건 POST 요청

        Args:
            endpoint: BASE_URL 기준 상대 경로 (예: "games")
            query: APIcalypse 쿼리 문자열

        Returns:
            JSON 응답 list

        Raises:
            IgdbAuthError:       HTTP 401
            IgdbRateLimitError:  HTTP 429
            IgdbNotFoundError:   HTTP 404
            IgdbServerError:     HTTP 5xx
        """
        url = f"{self.BASE_URL}/{endpoint}"
        resp = self._session.post(
            url,
            headers=self._headers(),
            data=query,
            timeout=_REQUEST_TIMEOUT,
        )

        if resp.status_code == 401:
            raise IgdbAuthError("IGDB 인증 실패 - 토큰 만료")
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 1))
            raise IgdbRateLimitError(retry_after=retry_after)
        if resp.status_code == 404:
            raise IgdbNotFoundError(f"Not found: {url}")
        if resp.status_code >= 500:
            raise IgdbServerError(
                f"IGDB 서버 오류 {resp.status_code}: {url}",
                status_code=resp.status_code,
            )

        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    def _post_with_auth_retry(self, endpoint: str, query: str) -> list[dict[str, Any]]:
        """401 발생 시 토큰 재발급 후 1회 재시도"""
        try:
            return self._post(endpoint, query)
        except IgdbAuthError:
            logger.warning("IGDB 토큰 만료, 재발급 후 재시도")
            self._access_token = self._fetch_token()
            return self._post(endpoint, query)

    def _paginate(
        self,
        endpoint: str,
        fields: str,
        where: str = "",
        sort: str = "updated_at desc",
    ) -> Generator[list[dict[str, Any]]]:
        """
        IGDB offset 기반 페이지네이션 제너레이터

        - 빈 결과 또는 _MAX_PAGES 초과 시 중단
        - 429 발생 시 Retry-After sleep 후 1회 재시도
        - 요청 간 _REQUEST_INTERVAL sleep
        """
        offset = 0
        page = 0

        while True:
            if page >= _MAX_PAGES:
                logger.warning("_MAX_PAGES(%d) 초과, 순회 중단", _MAX_PAGES)
                break

            where_clause = f"where {where};" if where else ""
            query = f"fields {fields};{where_clause}sort {sort};limit {_PAGE_SIZE};offset {offset};"

            try:
                results = self._post_with_auth_retry(endpoint, query)
            except IgdbRateLimitError as e:
                logger.warning("Rate limit, %ds 대기 후 재시도 (page=%d)", e.retry_after, page)
                time.sleep(e.retry_after)
                results = self._post_with_auth_retry(endpoint, query)

            if not results:
                break

            yield results

            if len(results) < _PAGE_SIZE:
                break

            offset += _PAGE_SIZE
            page += 1
            time.sleep(_REQUEST_INTERVAL)

    # 공개 인터페이스 ---------------------------------------------------

    def iter_games(self) -> Generator[list[dict[str, Any]]]:
        """
        GET /games 페이지 순회
        메인 게임만 (category=0), 주요 필드 포함
        """
        fields = (
            "id,name,slug,summary,"
            "first_release_date,"
            "rating,rating_count,"
            "cover.image_id,"
            "genres.id,genres.name,genres.slug,"
            "platforms.id,platforms.name,"
            "keywords.id,"
            "age_ratings.category,age_ratings.rating,"
            "screenshots.image_id,"
            "videos.video_id,videos.name,"
            "websites.url,websites.category,"
            "follows,updated_at"
        )
        yield from self._paginate("games", fields)

    def get_game(self, igdb_id: int) -> dict[str, Any]:
        """GET /games/{id} - 단건 상세 조회"""
        fields = (
            "id,name,slug,summary,storyline,"
            "first_release_date,status,"
            "cover.image_id,"
            "rating,rating_count,aggregated_rating,"
            "genres.id,genres.name,genres.slug,"
            "platforms.id,platforms.name,platforms.slug,"
            "keywords.id,keywords.name,keywords.slug,"
            "age_ratings.category,age_ratings.rating,"
            "screenshots.image_id,"
            "videos.video_id,videos.name,"
            "websites.url,websites.category,"
            "updated_at"
        )
        results = self._post_with_auth_retry("games", f"fields {fields}; where id = {igdb_id};")
        if not results:
            raise IgdbNotFoundError(f"Game not found: igdb_id={igdb_id}")
        return results[0]

    def search_games(
        self,
        *,
        query: str | None = None,
        genre_ids: list[int] | None = None,
        platform_ids: list[int] | None = None,
        tag_ids: list[int] | None = None,
        theme_ids: list[int] | None = None,
        game_mode_ids: list[int] | None = None,
        sort: str = "rating desc",
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        fields = (
            "id,name,slug,summary,"
            "first_release_date,"
            "rating,rating_count,"
            "cover.image_id,"
            "genres.id,genres.name,"
            "platforms.id,platforms.name,"
            "keywords.id,keywords.name,"
            "themes.id,themes.name,"
            "game_modes.id,game_modes.name,"
            "age_ratings.category,age_ratings.rating,"
            "follows"
        )

        where_parts: list[str] = []

        if genre_ids:
            ids_str = ",".join(str(i) for i in genre_ids)
            where_parts.append(f"genres = ({ids_str})")

        if platform_ids:
            ids_str = ",".join(str(i) for i in platform_ids)
            where_parts.append(f"platforms = ({ids_str})")

        if tag_ids:
            ids_str = ",".join(str(i) for i in tag_ids)
            where_parts.append(f"keywords = ({ids_str})")

        if theme_ids:
            ids_str = ",".join(str(i) for i in theme_ids)
            where_parts.append(f"themes = ({ids_str})")

        if game_mode_ids:
            ids_str = ",".join(str(i) for i in game_mode_ids)
            where_parts.append(f"game_modes = ({ids_str})")

        where_clause = " & ".join(where_parts)
        where_str = f"where {where_clause};" if where_clause else ""

        if query:
            q = f'search "{query}";fields {fields};{where_str}limit {limit};offset {offset};'
        else:
            q = f"fields {fields};{where_str}sort {sort};limit {limit};offset {offset};"

        return self._post_with_auth_retry("games", q)

    def get_games_by_ids(self, igdb_ids: list[int]) -> list[dict[str, Any]]:
        """
        여러 게임을 ID 리스트로 벌크 조회

        IGDB는 한 번에 최대 500개까지 조회 가능.
        500개 초과 시 청크로 나눠서 호출.
        """
        if not igdb_ids:
            return []

        fields = (
            "id,name,slug,summary,"
            "first_release_date,"
            "rating,rating_count,"
            "cover.image_id,"
            "genres.id,genres.name,"
            "platforms.id,platforms.name,"
            "keywords.id,keywords.name,"
            "age_ratings.category,age_ratings.rating,"
            "follows"
        )

        all_results: list[dict[str, Any]] = []
        for i in range(0, len(igdb_ids), _PAGE_SIZE):
            chunk = igdb_ids[i : i + _PAGE_SIZE]
            ids_str = ",".join(str(x) for x in chunk)
            query = f"fields {fields};where id = ({ids_str});limit {len(chunk)};"
            results = self._post_with_auth_retry("games", query)
            all_results.extend(results)
            if i + _PAGE_SIZE < len(igdb_ids):
                time.sleep(_REQUEST_INTERVAL)

        return all_results

    def iter_genres(self) -> Generator[list[dict[str, Any]]]:
        """GET /genres 페이지 순회"""
        yield from self._paginate("genres", "id,name,slug")

    def iter_platforms(self) -> Generator[list[dict[str, Any]]]:
        """GET /platforms 페이지 순회"""
        yield from self._paginate("platforms", "id,name,slug,platform_logo.image_id")

    def iter_keywords(self) -> Generator[list[dict[str, Any]]]:
        """GET /keywords 페이지 순회 (태그 대용)"""
        yield from self._paginate("keywords", "id,name,slug")


# 싱글턴 팩토리 ----------------------------------------------------------

_client_instance: IgdbClient | None = None


def get_igdb_client() -> IgdbClient:
    """프로세스당 하나의 IgdbClient 인스턴스 반환 (토큰 재사용)"""
    global _client_instance
    if _client_instance is None:
        _client_instance = IgdbClient()
    return _client_instance
