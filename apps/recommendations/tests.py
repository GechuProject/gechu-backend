from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.games.models import Game, GameGenre, GameTag, Genre, Tag
from apps.recommendations.models import RecommendationJob, UserRecommendation
from apps.users.models import User


class RecommendationListAPITestCase(TestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/recommendations/"

    def _create_user(self) -> User:
        return User.objects.create_user(
            email="rec-user@ex.com",
            nickname="rec-user",
            birth_date=date(1993, 1, 1),
            password="pw",
        )

    def _create_game(
        self,
        *,
        rawg_id: int,
        slug: str,
        name: str,
        is_visible: bool = True,
        esrb_rating: str = Game.EsrbRating.TEEN,
    ) -> Game:
        return Game.objects.create(
            rawg_id=rawg_id,
            slug=slug,
            name=name,
            thumbnail_img_url="https://example.com/thumb.jpg",
            website="https://example.com",
            rawg_rating=Decimal("4.70"),
            esrb_rating=esrb_rating,
            is_visible=is_visible,
        )

    def _create_recommendation(
        self,
        *,
        user: User,
        game: Game,
        rank: int,
        reason: str | None,
        score: Decimal = Decimal("0.8612"),
    ) -> UserRecommendation:
        now = timezone.now()
        return UserRecommendation.objects.create(
            user=user,
            game=game,
            generation_version=1,
            score=score,
            rank=rank,
            reason=reason,
            generated_at=now,
            expires_at=now + timedelta(days=7),
        )

    def test_recommendation_list_unauthorized(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_recommendation_list_not_ready_when_job_pending(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.PENDING,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 202)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "RECOMMENDATION_NOT_READY")
        self.assertEqual(
            RecommendationJob.objects.filter(
                target_user=user,
                job_type=RecommendationJob.JobType.USER_REFRESH,
            ).count(),
            1,
        )

    def test_recommendation_list_not_ready_when_no_recommendation(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 202)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data.get("code"), "RECOMMENDATION_NOT_READY")
        queued_job = RecommendationJob.objects.filter(
            target_user=user,
            job_type=RecommendationJob.JobType.USER_REFRESH,
        ).first()
        self.assertIsNotNone(queued_job)
        self.assertEqual(cast(RecommendationJob, queued_job).status, RecommendationJob.Status.PENDING)

    def test_recommendation_list_success(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        game = self._create_game(rawg_id=7001, slug="cp2077", name="Cyberpunk 2077")
        genre = Genre.objects.create(rawg_id=1, name="Action", slug="action")
        tag = Tag.objects.create(rawg_id=10, name="RPG", slug="rpg")
        GameGenre.objects.create(game=game, genre=genre)
        GameTag.objects.create(game=game, tag=tag)
        self._create_recommendation(user=user, game=game, rank=1, reason=UserRecommendation.ReasonType.HYBRID)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, Any], response.data)
        self.assertIn("results", payload)
        self.assertEqual(len(payload["results"]), 1)
        item = payload["results"][0]
        self.assertEqual(item["game_id"], game.id)
        self.assertEqual(item["name"], "Cyberpunk 2077")
        self.assertEqual(item["reason"], "hybrid")
        self.assertEqual(item["rank"], 1)
        self.assertEqual(item["tags"], ["RPG"])
        self.assertEqual(item["genres"][0]["name"], "Action")

    def test_recommendation_list_filters_type_genre_tag_and_is_adult(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        game_action = self._create_game(
            rawg_id=7002, slug="action-game", name="Action Game", esrb_rating=Game.EsrbRating.ADULTS_ONLY
        )
        game_puzzle = self._create_game(
            rawg_id=7003, slug="puzzle-game", name="Puzzle Game", esrb_rating=Game.EsrbRating.TEEN
        )

        genre_action = Genre.objects.create(rawg_id=2, name="Action", slug="action-2")
        genre_puzzle = Genre.objects.create(rawg_id=3, name="Puzzle", slug="puzzle")
        tag_rpg = Tag.objects.create(rawg_id=11, name="RPG", slug="rpg-2")
        tag_cozy = Tag.objects.create(rawg_id=12, name="Cozy", slug="cozy")

        GameGenre.objects.create(game=game_action, genre=genre_action)
        GameGenre.objects.create(game=game_puzzle, genre=genre_puzzle)
        GameTag.objects.create(game=game_action, tag=tag_rpg)
        GameTag.objects.create(game=game_puzzle, tag=tag_cozy)

        self._create_recommendation(
            user=user, game=game_action, rank=1, reason=UserRecommendation.ReasonType.SIMILARITY
        )
        self._create_recommendation(
            user=user, game=game_puzzle, rank=2, reason=UserRecommendation.ReasonType.PREFERENCE
        )

        response = self.client.get(
            self.url,
            {"type": "similarity", "genre": str(genre_action.id), "tag": str(tag_rpg.id), "is_adult": "true"},
        )
        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["name"], "Action Game")

    def test_recommendation_list_invalid_query_param_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        game = self._create_game(rawg_id=7004, slug="dummy", name="Dummy")
        self._create_recommendation(user=user, game=game, rank=1, reason=UserRecommendation.ReasonType.HYBRID)

        response = self.client.get(self.url, {"type": "wrong"})
        self.assertEqual(response.status_code, 400)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(payload["code"], "INVALID_QUERY_PARAM")
