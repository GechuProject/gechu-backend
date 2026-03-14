from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.games.models import Game, GameGenre, GameTag, Genre, Tag
from apps.interactions.models import InteractionLog
from apps.recommendations.models import RecommendationJob, UserRecommendation
from apps.recommendations.tasks import (
    _build_fallback_candidates,
    _build_similarity_candidates,
    _collect_seed_game_ids,
    _upsert_recommendations,
    process_pending_recommendation_jobs,
    run_user_refresh_job,
)
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

    def test_recommendation_list_invalid_genre_query_param_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url, {"genre": "not-a-number"})
        self.assertEqual(response.status_code, 400)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(payload["code"], "INVALID_QUERY_PARAM")


class RecommendationStatusAPITestCase(TestCase):
    client: APIClient

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/recommendations/status/"
        self.user = User.objects.create_user(
            email="status-user@ex.com",
            nickname="status-user",
            birth_date=date(1991, 1, 1),
            password="pw",
        )

    def _create_game(self, *, rawg_id: int, slug: str, name: str) -> Game:
        return Game.objects.create(
            rawg_id=rawg_id,
            slug=slug,
            name=name,
            thumbnail_img_url="https://example.com/thumb.jpg",
            website="https://example.com",
            rawg_rating=Decimal("4.10"),
            is_visible=True,
        )

    def _create_recommendation(self, *, generation: int) -> UserRecommendation:
        game = self._create_game(rawg_id=9000 + generation, slug=f"status-{generation}", name=f"Status {generation}")
        now = timezone.now()
        return UserRecommendation.objects.create(
            user=self.user,
            game=game,
            generation_version=generation,
            score=Decimal("0.9000"),
            rank=1,
            reason=UserRecommendation.ReasonType.SIMILARITY,
            generated_at=now,
            expires_at=now + timedelta(days=7),
        )

    def test_status_unauthorized(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_status_pending_when_no_job_and_no_recommendation(self) -> None:
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["generation"])
        self.assertIsNone(data["generated_at"])
        self.assertIsNone(data["expires_at"])

    def test_status_pending_when_job_running(self) -> None:
        rec = self._create_recommendation(generation=2)
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.user,
            status=RecommendationJob.Status.RUNNING,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["generation"], rec.generation_version)

    def test_status_success_when_job_success_and_recommendation_exists(self) -> None:
        rec = self._create_recommendation(generation=3)
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.user,
            status=RecommendationJob.Status.SUCCESS,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["generation"], rec.generation_version)

    def test_status_pending_when_job_success_but_no_recommendation(self) -> None:
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.user,
            status=RecommendationJob.Status.SUCCESS,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["generation"])

    def test_status_failed_when_job_failed(self) -> None:
        rec = self._create_recommendation(generation=4)
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.user,
            status=RecommendationJob.Status.FAILED,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["generation"], rec.generation_version)


class RecommendationTaskTestCase(TestCase):
    def _create_user(self) -> User:
        return User.objects.create_user(
            email="task-user@ex.com",
            nickname="task-user",
            birth_date=date(1992, 1, 1),
            password="pw",
        )

    def _create_game(
        self,
        *,
        rawg_id: int,
        slug: str,
        name: str,
        rawg_rating: Decimal = Decimal("4.20"),
        esrb_rating: str = Game.EsrbRating.TEEN,
        is_visible: bool = True,
    ) -> Game:
        return Game.objects.create(
            rawg_id=rawg_id,
            slug=slug,
            name=name,
            thumbnail_img_url="https://example.com/thumb.jpg",
            website="https://example.com",
            rawg_rating=rawg_rating,
            esrb_rating=esrb_rating,
            is_visible=is_visible,
        )

    def test_collect_seed_game_ids_returns_latest_unique_ids(self) -> None:
        user = self._create_user()
        g1 = self._create_game(rawg_id=8001, slug="g1", name="Game 1")
        g2 = self._create_game(rawg_id=8002, slug="g2", name="Game 2")
        g3 = self._create_game(rawg_id=8003, slug="g3", name="Game 3")

        now = timezone.now()
        l1 = InteractionLog.objects.create(
            user=user, game=g1, type=InteractionLog.ActionType.VIEW, source=InteractionLog.SourceType.DETAIL_PAGE
        )
        l2 = InteractionLog.objects.create(
            user=user, game=g2, type=InteractionLog.ActionType.VIEW, source=InteractionLog.SourceType.DETAIL_PAGE
        )
        l3 = InteractionLog.objects.create(
            user=user, game=g1, type=InteractionLog.ActionType.VIEW, source=InteractionLog.SourceType.DETAIL_PAGE
        )
        l4 = InteractionLog.objects.create(
            user=user, game=g3, type=InteractionLog.ActionType.VIEW, source=InteractionLog.SourceType.DETAIL_PAGE
        )
        InteractionLog.objects.filter(id=l1.id).update(created_at=now - timedelta(minutes=4))
        InteractionLog.objects.filter(id=l2.id).update(created_at=now - timedelta(minutes=3))
        InteractionLog.objects.filter(id=l3.id).update(created_at=now - timedelta(minutes=2))
        InteractionLog.objects.filter(id=l4.id).update(created_at=now - timedelta(minutes=1))

        seed_ids = _collect_seed_game_ids(user_id=user.id)
        self.assertEqual(seed_ids, [g3.id, g1.id, g2.id])

    def test_build_similarity_candidates_filters_adult_for_non_verified_user(self) -> None:
        seed = self._create_game(rawg_id=8010, slug="seed", name="Seed")
        teen = self._create_game(rawg_id=8011, slug="teen", name="Teen", esrb_rating=Game.EsrbRating.TEEN)
        adult = self._create_game(rawg_id=8012, slug="adult", name="Adult", esrb_rating=Game.EsrbRating.ADULTS_ONLY)

        from apps.recommendations.models import GameSimilarity

        GameSimilarity.objects.create(game=seed, similar_game=teen, score=Decimal("0.7000"))
        GameSimilarity.objects.create(game=seed, similar_game=adult, score=Decimal("0.9000"))

        non_adult_candidates = _build_similarity_candidates(seed_game_ids=[seed.id], is_adult_verified=False)
        self.assertEqual(non_adult_candidates, [(teen.id, Decimal("0.7000"))])

        adult_candidates = _build_similarity_candidates(seed_game_ids=[seed.id], is_adult_verified=True)
        self.assertEqual(adult_candidates, [(adult.id, Decimal("0.9000")), (teen.id, Decimal("0.7000"))])

    def test_build_fallback_candidates_applies_visibility_and_adult_filter(self) -> None:
        teen = self._create_game(rawg_id=8021, slug="f-teen", name="Fallback Teen", rawg_rating=Decimal("4.80"))
        self._create_game(
            rawg_id=8022,
            slug="f-adult",
            name="Fallback Adult",
            rawg_rating=Decimal("4.90"),
            esrb_rating=Game.EsrbRating.ADULTS_ONLY,
        )
        self._create_game(
            rawg_id=8023,
            slug="f-hidden",
            name="Fallback Hidden",
            rawg_rating=Decimal("5.00"),
            is_visible=False,
        )

        non_adult = _build_fallback_candidates(is_adult_verified=False)
        self.assertEqual(non_adult, [(teen.id, Decimal("0.9600"))])

    def test_upsert_recommendations_replaces_old_generation(self) -> None:
        user = self._create_user()
        old_game = self._create_game(rawg_id=8031, slug="old-game", name="Old")
        g1 = self._create_game(rawg_id=8032, slug="new-g1", name="New 1")
        g2 = self._create_game(rawg_id=8033, slug="new-g2", name="New 2")
        now = timezone.now()
        UserRecommendation.objects.create(
            user=user,
            game=old_game,
            generation_version=1,
            score=Decimal("0.1000"),
            rank=1,
            reason=UserRecommendation.ReasonType.SIMILARITY,
            generated_at=now,
            expires_at=now + timedelta(days=1),
        )

        _upsert_recommendations(
            user_id=user.id,
            generation_version=2,
            candidates=[(g1.id, Decimal("0.9000")), (g2.id, Decimal("0.8000"))],
        )

        recs = UserRecommendation.objects.filter(user=user).order_by("rank")
        self.assertEqual(recs.count(), 2)
        self.assertEqual([recs[0].game_id, recs[1].game_id], [g1.id, g2.id])
        self.assertTrue(all(rec.generation_version == 2 for rec in recs))

    def test_run_user_refresh_job_success(self) -> None:
        user = self._create_user()
        seed = self._create_game(rawg_id=8041, slug="seed-job", name="Seed Job")
        similar = self._create_game(rawg_id=8042, slug="sim-job", name="Similar Job")
        InteractionLog.objects.create(
            user=user,
            game=seed,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )

        from apps.recommendations.models import GameSimilarity

        GameSimilarity.objects.create(game=seed, similar_game=similar, score=Decimal("0.8800"))
        job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.PENDING,
        )

        run_user_refresh_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, RecommendationJob.Status.SUCCESS)
        self.assertIsNotNone(job.finished_at)
        self.assertTrue(UserRecommendation.objects.filter(user=user, game=similar).exists())

    def test_run_user_refresh_job_failure_marks_failed(self) -> None:
        user = self._create_user()
        job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.PENDING,
        )

        with patch("apps.recommendations.tasks.User.objects.get", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                run_user_refresh_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, RecommendationJob.Status.FAILED)
        self.assertEqual(job.retry_count, 1)
        self.assertIn("boom", cast(str, job.error_message))

    def test_run_user_refresh_job_skips_when_job_already_running(self) -> None:
        user = self._create_user()
        job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.RUNNING,
            started_at=timezone.now(),
        )

        run_user_refresh_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, RecommendationJob.Status.RUNNING)
        self.assertFalse(UserRecommendation.objects.filter(user=user).exists())

    def test_process_pending_recommendation_jobs_enqueues_pending_only(self) -> None:
        user = self._create_user()
        pending_1 = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.PENDING,
        )
        pending_2 = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.PENDING,
        )
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.SUCCESS,
        )

        with patch("apps.recommendations.tasks.process_user_refresh_job.delay") as mocked_delay:
            queued = process_pending_recommendation_jobs(limit=20)

        self.assertEqual(queued, 2)
        mocked_delay.assert_any_call(pending_1.id)
        mocked_delay.assert_any_call(pending_2.id)
