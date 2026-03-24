from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.games.serializers.game_detail import GameDetailSerializer
from apps.games.services.game_detail import GameDetailService


@extend_schema(
    tags=["games"],
    summary="게임 상세 정보 조회",
    description="게임 상세 정보를 조회합니다. (IGDB API 기반)",
    responses={
        200: GameDetailSerializer,
        403: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="성인 인증이 필요합니다.",
            examples=[
                OpenApiExample(
                    "성인 인증 필요",
                    value={
                        "status_code": ErrorMessages.ADULT_VERIFICATION_REQUIRED.status_code,
                        "code": ErrorMessages.ADULT_VERIFICATION_REQUIRED.name,
                        "message": ErrorMessages.ADULT_VERIFICATION_REQUIRED.message,
                    },
                ),
            ],
        ),
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="게임을 찾을 수 없습니다.",
            examples=[
                OpenApiExample(
                    "게임 존재하지 않음",
                    value={
                        "status_code": ErrorMessages.GAME_NOT_FOUND.status_code,
                        "code": ErrorMessages.GAME_NOT_FOUND.name,
                        "message": ErrorMessages.GAME_NOT_FOUND.message,
                    },
                ),
            ],
        ),
    },
)
class GameDetailView(APIView):
    def get(self, request: Request, game_id: int) -> Response:
        game = GameDetailService.detail_game(
            game_id=game_id,
            user=request.user,
        )

        serializer = GameDetailSerializer(game)

        return Response(serializer.data, status=status.HTTP_200_OK)
