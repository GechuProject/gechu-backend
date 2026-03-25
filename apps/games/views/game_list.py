from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.games.serializers.game_list import (
    GameListQuerySerializer,
    GameListResponseSerializer,
)
from apps.games.services.game_list import GameService
from apps.users.models import User
from apps.users.services.search_recent_service import save_recent_search_keyword


@extend_schema(
    tags=["games"],
    summary="게임 목록 조회",
    description="""게임 목록 조회 (검색/필터/정렬) - IGDB API 기반
        \n **장르 (genre_ids)**
        \n - id name - slug (igdb_id)
        \n - 1  RPG - rpg (12)
        \n - 2  어드벤처 - adventure (31)
        \n - 3  FPS - shooter (5)
        \n - 4  전략 - strategy (15)
        \n - 5  시뮬레이션 - simulator (13)
        \n - 6  스포츠 - sport (14)
        \n - 7  레이싱 - racing (10)
        \n - 8  퍼즐 - puzzle (9)
        \n - 9  격투 - fighting (4)
        \n - 10 아케이드 - arcade (33)
        \n **플랫폼 (platform_ids)**
        \n - id name - slug (igdb_id)
        \n - 1  PC - pc (6)
        \n - 2  PlayStation - playstation (167)
        \n - 3  Xbox - xbox (169)
        \n - 4  Nintendo Switch - nintendo-switch (130)
        \n - 5  Mobile - mobile (34)
        \n **태그 (tag_ids)**
        \n - id name - slug (igdb_id)
        \n - 1  오픈월드 - open-world (38)
        \n - 2  스토리 중심 - story-rich (2426)
        \n - 3  Co-op - co-op (3)
        \n - 4  PvP - pvp (546)
        \n - 5  싱글플레이 - single-player (1)
        \n - 6  멀티플레이 - multiplayer (2)
        \n - 7  생존 - survival (21)
        \n - 8  공포 - horror (19)
        \n - 9  판타지 - fantasy (17)
        \n - 10 SF - science-fiction (18)
""",
    parameters=[
        OpenApiParameter("search", type=str, required=False, description="게임 이름 검색"),
        OpenApiParameter("genre_ids", type=str, required=False, description="장르 ID 리스트(콤마 구분)"),
        OpenApiParameter(
            "genre_name", type=str, required=False, description="단일 장르 TOP 10 조회. 다른 필터/정렬/페이지는 무시"
        ),
        OpenApiParameter("platform_ids", type=str, required=False, description="플랫폼 ID 리스트(콤마 구분)"),
        OpenApiParameter("tag_ids", type=str, required=False, description="태그 ID 리스트(콤마 구분)"),
        OpenApiParameter(
            "ordering",
            type=str,
            required=False,
            description="정렬",
            enum=["rawg_rating", "-rawg_rating", "released", "-released", "rawg_added", "-rawg_added"],
        ),
        OpenApiParameter("page", type=int, required=False, description="조회할 페이지 번호"),
        OpenApiParameter("page_size", type=int, required=False, description="페이지당 결과 수(최대: 100)"),
    ],
    responses={
        200: GameListResponseSerializer,
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Bad Request",
            examples=[
                OpenApiExample(
                    "잘못된 쿼리 파라미터",
                    value={
                        "status_code": ErrorMessages.INVALID_QUERY_PARAM.status_code,
                        "code": ErrorMessages.INVALID_QUERY_PARAM.name,
                        "message": ErrorMessages.INVALID_QUERY_PARAM.message,
                    },
                ),
                OpenApiExample(
                    "지원하지 않는 정렬 기준",
                    value={
                        "status_code": ErrorMessages.INVALID_ORDERING.status_code,
                        "code": ErrorMessages.INVALID_ORDERING.name,
                        "message": ErrorMessages.INVALID_ORDERING.message,
                    },
                ),
                OpenApiExample(
                    "존재하지 않는 장르 ID",
                    value={
                        "status_code": ErrorMessages.INVALID_GENRE_ID.status_code,
                        "code": ErrorMessages.INVALID_GENRE_ID.name,
                        "message": ErrorMessages.INVALID_GENRE_ID.message,
                    },
                ),
                OpenApiExample(
                    "존재하지 않는 플랫폼 ID",
                    value={
                        "status_code": ErrorMessages.INVALID_PLATFORM_ID.status_code,
                        "code": ErrorMessages.INVALID_PLATFORM_ID.name,
                        "message": ErrorMessages.INVALID_PLATFORM_ID.message,
                    },
                ),
                OpenApiExample(
                    "존재하지 않는 태그 ID",
                    value={
                        "status_code": ErrorMessages.INVALID_TAG_ID.status_code,
                        "code": ErrorMessages.INVALID_TAG_ID.name,
                        "message": ErrorMessages.INVALID_TAG_ID.message,
                    },
                ),
            ],
        ),
    },
)
class GameListView(APIView):
    def get(self, request: Request) -> Response:
        query_serializer = GameListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        data = query_serializer.validated_data
        if self.request.user.is_authenticated and data.get("search"):
            save_recent_search_keyword(user=self.request.user, keyword=data["search"])

        page = data.get("page", 1)
        page_size = data.get("page_size", 20)

        genre_name = data.get("genre_name")
        genre_ids = data.get("genre_ids")

        user: User | None = request.user if request.user.is_authenticated else None

        # TOP 10 로직: genre_name 또는 단일 genre_id + page=1 + page_size=10
        use_top_10 = False
        if genre_name:
            use_top_10 = True
        elif genre_ids and len(genre_ids) == 1 and page == 1 and page_size == 10:
            # genre_id를 genre_name으로 변환
            from apps.games.models import Genre

            genre = Genre.objects.filter(id=genre_ids[0]).first()
            if genre:
                genre_name = genre.name
                use_top_10 = True

        if use_top_10 and genre_name:
            items = GameService.top_n_by_genre(
                genre_name,
                user=user,
            )
            next_url = None
            previous_url = None
        else:
            results = GameService.list_games(
                search=data.get("search"),
                genre_ids=data.get("genre_ids"),
                platform_ids=data.get("platform_ids"),
                tag_ids=data.get("tag_ids"),
                ordering=data.get("ordering"),
                page=page,
                page_size=page_size,
                user=user,
            )

            # has_next 판단: page_size+1 개를 요청해서
            has_next = len(results) > page_size
            items = results[:page_size]

            # next/previous URL 개선 (기존 필터 유지)
            query_params = request.GET.copy()
            if has_next:
                query_params["page"] = page + 1
                next_url = f"{request.path}?{query_params.urlencode()}"
            else:
                next_url = None

            if page > 1:
                query_params["page"] = page - 1
                previous_url = f"{request.path}?{query_params.urlencode()}"
            else:
                previous_url = None

        response_data = {
            "next": next_url,
            "previous": previous_url,
            "results": items,
        }

        serializer = GameListResponseSerializer(response_data)

        return Response(serializer.data, status=status.HTTP_200_OK)
