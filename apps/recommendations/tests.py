from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.testcase import FastTestCase
from apps.interactions.models import InteractionLog
from apps.recommendations.models import GameSimilarity, RecommendationJob, UserRecommendation
from apps.recommendations.tasks import (
    _build_similarity_candidates,
    _collect_seed_game_ids,
    _upsert_recommendations,
    process_pending_recommendation_jobs,
    run_similarity_rebuild_job,
    run_user_refresh_job,
)
from apps.users.models import User

# IGDB game IDs (no DB Game model)
IGDB_GAME_CP2077 = 7001
IGDB_GAME_ACTION = 7002
IGDB_GAME_PUZZLE = 7003
IGDB_GAME_DUMMY = 7004


class RecommendationListAPITestCase(FastTestCase):
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

    def _create_recommendation(
        self,
        *,
        user: User,
        igdb_game_id: int,
        rank: int,
        reason: str | None,
        score: Decimal = Decimal("0.8612"),
    ) -> UserRecommendation:
        now = timezone.now()
        return UserRecommendation.objects.create(
            user=user,
            igdb_game_id=igdb_game_id,
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

    @patch("apps.recommendations.views.igdb_cache.get_games_by_ids")
    def test_recommendation_list_success(self, mock_get_games: object) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        self._create_recommendation(
            user=user, igdb_game_id=IGDB_GAME_CP2077, rank=1, reason=UserRecommendation.ReasonType.HYBRID
        )

        mock_get_games.return_value = [  # type: ignore[attr-defined]
            {
                "id": IGDB_GAME_CP2077,
                "name": "Cyberpunk 2077",
                "slug": "cp2077",
                "thumbnail_img_url": "https://example.com/thumb.jpg",
                "rawg_rating": Decimal("4.70"),
                "genres": [{"id": 1, "name": "Action", "slug": "action"}],
            }
        ]

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, Any], response.data)
        self.assertIn("results", payload)
        self.assertEqual(len(payload["results"]), 1)
        item = payload["results"][0]
        self.assertEqual(item["game"]["id"], IGDB_GAME_CP2077)
        self.assertEqual(item["game"]["name"], "Cyberpunk 2077")
        self.assertEqual(item["reason"], "hybrid")
        self.assertEqual(item["rank"], 1)
        self.assertEqual(item["game"]["genres"][0]["name"], "Action")

    def test_recommendation_list_invalid_query_param_returns_400(self) -> None:
        user = self._create_user()
        self.client.force_authenticate(user=user)
        self._create_recommendation(
            user=user, igdb_game_id=IGDB_GAME_DUMMY, rank=1, reason=UserRecommendation.ReasonType.HYBRID
        )

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


class RecommendationStatusAPITestCase(FastTestCase):
    client: APIClient
    user: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create_user(
            email="status-user@ex.com",
            nickname="status-user",
            birth_date=date(1991, 1, 1),
            password="pw",
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/recommendations/status/"
        self.user.refresh_from_db()

    def _create_recommendation(self, *, generation: int) -> UserRecommendation:
        igdb_game_id = 9000 + generation
        now = timezone.now()
        return UserRecommendation.objects.create(
            user=self.user,
            igdb_game_id=igdb_game_id,
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
        self.assertIsNone(data["generation_version"])
        self.assertIsNone(data["generated_at"])
        self.assertIsNone(data["expires_at"])

    def test_status_running_when_job_running(self) -> None:
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
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["generation_version"], rec.generation_version)

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
        self.assertEqual(data["generation_version"], rec.generation_version)

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
        self.assertIsNone(data["generation_version"])

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
        self.assertEqual(data["generation_version"], rec.generation_version)


class RecommendationTaskTestCase(FastTestCase):
    def _create_user(self) -> User:
        return User.objects.create_user(
            email="task-user@ex.com",
            nickname="task-user",
            birth_date=date(1992, 1, 1),
            password="pw",
        )

    def test_collect_seed_game_ids_returns_latest_unique_ids(self) -> None:
        user = self._create_user()
        igdb_g1 = 8001
        igdb_g2 = 8002
        igdb_g3 = 8003

        now = timezone.now()
        l1 = InteractionLog.objects.create(
            user=user,
            igdb_game_id=igdb_g1,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )
        l2 = InteractionLog.objects.create(
            user=user,
            igdb_game_id=igdb_g2,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )
        l3 = InteractionLog.objects.create(
            user=user,
            igdb_game_id=igdb_g1,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )
        l4 = InteractionLog.objects.create(
            user=user,
            igdb_game_id=igdb_g3,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )
        InteractionLog.objects.filter(id=l1.id).update(created_at=now - timedelta(minutes=4))
        InteractionLog.objects.filter(id=l2.id).update(created_at=now - timedelta(minutes=3))
        InteractionLog.objects.filter(id=l3.id).update(created_at=now - timedelta(minutes=2))
        InteractionLog.objects.filter(id=l4.id).update(created_at=now - timedelta(minutes=1))

        seed_ids = _collect_seed_game_ids(user_id=user.id)
        self.assertEqual(seed_ids, [igdb_g3, igdb_g1, igdb_g2])

    def test_build_similarity_candidates(self) -> None:
        igdb_seed = 8010
        igdb_teen = 8011
        igdb_adult = 8012

        GameSimilarity.objects.create(igdb_game_id=igdb_seed, igdb_similar_game_id=igdb_teen, score=Decimal("0.7000"))
        GameSimilarity.objects.create(igdb_game_id=igdb_seed, igdb_similar_game_id=igdb_adult, score=Decimal("0.9000"))

        candidates = _build_similarity_candidates(seed_game_ids=[igdb_seed])
        # Both candidates returned, ordered by score desc
        self.assertEqual(candidates, [(igdb_adult, Decimal("0.9000")), (igdb_teen, Decimal("0.7000"))])

    def test_upsert_recommendations_replaces_old_generation(self) -> None:
        user = self._create_user()
        igdb_old = 8031
        igdb_g1 = 8032
        igdb_g2 = 8033
        now = timezone.now()
        UserRecommendation.objects.create(
            user=user,
            igdb_game_id=igdb_old,
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
            candidates=[(igdb_g1, Decimal("0.9000")), (igdb_g2, Decimal("0.8000"))],
        )

        recs = UserRecommendation.objects.filter(user=user).order_by("rank")
        self.assertEqual(recs.count(), 2)
        self.assertEqual([recs[0].igdb_game_id, recs[1].igdb_game_id], [igdb_g1, igdb_g2])
        self.assertTrue(all(rec.generation_version == 2 for rec in recs))

    def test_run_user_refresh_job_success(self) -> None:
        user = self._create_user()
        igdb_seed = 8041
        igdb_similar = 8042
        InteractionLog.objects.create(
            user=user,
            igdb_game_id=igdb_seed,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )

        GameSimilarity.objects.create(
            igdb_game_id=igdb_seed, igdb_similar_game_id=igdb_similar, score=Decimal("0.8800")
        )
        job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.PENDING,
        )

        run_user_refresh_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, RecommendationJob.Status.SUCCESS)
        self.assertIsNotNone(job.finished_at)
        self.assertTrue(UserRecommendation.objects.filter(user=user, igdb_game_id=igdb_similar).exists())

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

    def test_run_similarity_rebuild_job_success(self) -> None:
        user_a = self._create_user()
        user_b = User.objects.create_user(
            email="rec-user2@ex.com",
            nickname="rec-user2",
            birth_date=date(1994, 1, 1),
            password="pw",
        )

        InteractionLog.objects.create(
            user=user_a,
            igdb_game_id=9001,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )
        InteractionLog.objects.create(
            user=user_a,
            igdb_game_id=9002,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )
        InteractionLog.objects.create(
            user=user_b,
            igdb_game_id=9001,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )
        InteractionLog.objects.create(
            user=user_b,
            igdb_game_id=9002,
            type=InteractionLog.ActionType.VIEW,
            source=InteractionLog.SourceType.DETAIL_PAGE,
        )

        job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.SIMILARITY_REBUILD,
            target_user=None,
            status=RecommendationJob.Status.PENDING,
        )
        run_similarity_rebuild_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, RecommendationJob.Status.SUCCESS)
        self.assertTrue(GameSimilarity.objects.filter(igdb_game_id=9001, igdb_similar_game_id=9002).exists())

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

    def test_process_pending_recommendation_jobs_enqueues_similarity_rebuild(self) -> None:
        similarity_job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.SIMILARITY_REBUILD,
            target_user=None,
            status=RecommendationJob.Status.PENDING,
        )

        with patch("apps.recommendations.tasks.process_similarity_rebuild_job.delay") as mocked_delay:
            queued = process_pending_recommendation_jobs(limit=20)

        self.assertEqual(queued, 1)
        mocked_delay.assert_called_once_with(similarity_job.id)
        similarity_job.refresh_from_db()
        self.assertEqual(similarity_job.status, RecommendationJob.Status.RUNNING)

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

    def test_process_pending_recommendation_jobs_claims_jobs_as_running_before_enqueue(self) -> None:
        user = self._create_user()
        job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.PENDING,
        )

        with patch("apps.recommendations.tasks.process_user_refresh_job.delay"):
            queued = process_pending_recommendation_jobs(limit=20)

        self.assertEqual(queued, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, RecommendationJob.Status.RUNNING)
        self.assertIsNone(job.started_at)


class AdminRecommendationJobListAPITestCase(FastTestCase):
    client: APIClient
    admin_user: User
    normal_user: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin_user = User.objects.create_user(
            email="admin-rec@ex.com",
            nickname="admin-rec",
            birth_date=date(1990, 1, 1),
            password="pw",
            is_staff=True,
        )
        cls.normal_user = User.objects.create_user(
            email="normal-rec@ex.com",
            nickname="normal-rec",
            birth_date=date(1994, 1, 1),
            password="pw",
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/admin/recommendation-jobs/"
        self.admin_user.refresh_from_db()
        self.normal_user.refresh_from_db()

    def test_admin_recommendation_job_list_unauthorized(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_admin_recommendation_job_list_forbidden_for_non_admin(self) -> None:
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["code"], ErrorMessages.FORBIDDEN.name)

    def test_admin_recommendation_job_list_success(self) -> None:
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.normal_user,
            status=RecommendationJob.Status.PENDING,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["type"], RecommendationJob.JobType.USER_REFRESH)
        self.assertEqual(payload["results"][0]["status"], RecommendationJob.Status.PENDING)
        self.assertEqual(payload["results"][0]["target_user"], self.normal_user.id)

    def test_admin_recommendation_job_list_filters_status_and_type(self) -> None:
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.normal_user,
            status=RecommendationJob.Status.FAILED,
        )
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.SIMILARITY_REBUILD,
            target_user=None,
            status=RecommendationJob.Status.FAILED,
        )
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.normal_user,
            status=RecommendationJob.Status.SUCCESS,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url, {"status": "failed", "type": "user_refresh"})

        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["status"], RecommendationJob.Status.FAILED)
        self.assertEqual(payload["results"][0]["type"], RecommendationJob.JobType.USER_REFRESH)

    def test_admin_recommendation_job_list_invalid_query_param_returns_400(self) -> None:
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url, {"status": "wrong"})

        self.assertEqual(response.status_code, 400)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(payload["code"], ErrorMessages.INVALID_QUERY_PARAM.name)

    def test_admin_recommendation_job_list_orders_by_created_at_desc(self) -> None:
        old_job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.normal_user,
            status=RecommendationJob.Status.PENDING,
        )
        new_job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.normal_user,
            status=RecommendationJob.Status.RUNNING,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, Any], response.data)
        result_ids = [row["id"] for row in payload["results"]]
        self.assertEqual(result_ids, [new_job.id, old_job.id])

    def test_admin_recommendation_job_list_supports_page_size(self) -> None:
        for _ in range(3):
            RecommendationJob.objects.create(
                job_type=RecommendationJob.JobType.USER_REFRESH,
                target_user=self.normal_user,
                status=RecommendationJob.Status.PENDING,
            )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url, {"page": 1, "page_size": 2})

        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(payload["count"], 3)
        self.assertEqual(len(payload["results"]), 2)


class AdminRecommendationJobDetailAPITestCase(FastTestCase):
    client: APIClient
    admin_user: User
    normal_user: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin_user = User.objects.create_user(
            email="admin-detail@ex.com",
            nickname="admin-detail",
            birth_date=date(1990, 1, 1),
            password="pw",
            is_staff=True,
        )
        cls.normal_user = User.objects.create_user(
            email="normal-detail@ex.com",
            nickname="normal-detail",
            birth_date=date(1994, 1, 1),
            password="pw",
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.admin_user.refresh_from_db()
        self.normal_user.refresh_from_db()

    def _url(self, job_id: int) -> str:
        return f"/api/v1/admin/recommendation-jobs/{job_id}/"

    def test_admin_recommendation_job_detail_unauthorized(self) -> None:
        job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.normal_user,
            status=RecommendationJob.Status.PENDING,
        )
        response = self.client.get(self._url(job.id))
        self.assertEqual(response.status_code, 401)

    def test_admin_recommendation_job_detail_forbidden_for_non_admin(self) -> None:
        job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.normal_user,
            status=RecommendationJob.Status.PENDING,
        )
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(self._url(job.id))

        self.assertEqual(response.status_code, 403)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["code"], ErrorMessages.FORBIDDEN.name)

    def test_admin_recommendation_job_detail_not_found(self) -> None:
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self._url(999999))

        self.assertEqual(response.status_code, 404)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["code"], ErrorMessages.JOB_NOT_FOUND.name)

    def test_admin_recommendation_job_detail_success(self) -> None:
        job = RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=self.normal_user,
            status=RecommendationJob.Status.FAILED,
            error_message="Connection timeout",
            started_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self._url(job.id))

        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(payload["id"], job.id)
        self.assertEqual(payload["type"], RecommendationJob.JobType.USER_REFRESH)
        self.assertEqual(payload["status"], RecommendationJob.Status.FAILED)
        self.assertEqual(payload["target_user"], self.normal_user.id)
        self.assertEqual(payload["error_message"], "Connection timeout")
        self.assertIsNotNone(payload["started_at"])
        self.assertIsNotNone(payload["created_at"])


class AdminRecommendationJobRunAPITestCase(FastTestCase):
    client: APIClient
    admin_user: User
    normal_user: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin_user = User.objects.create_user(
            email="admin-run@ex.com",
            nickname="admin-run",
            birth_date=date(1990, 1, 1),
            password="pw",
            is_staff=True,
        )
        cls.normal_user = User.objects.create_user(
            email="normal-run@ex.com",
            nickname="normal-run",
            birth_date=date(1994, 1, 1),
            password="pw",
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = "/api/v1/admin/recommendation-jobs/run/"
        self.admin_user.refresh_from_db()
        self.normal_user.refresh_from_db()

    def test_admin_recommendation_job_run_unauthorized(self) -> None:
        response = self.client.post(self.url, data={"job_type": "user_refresh"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_admin_recommendation_job_run_forbidden_for_non_admin(self) -> None:
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(self.url, data={"job_type": "user_refresh"}, format="json")

        self.assertEqual(response.status_code, 403)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["code"], ErrorMessages.FORBIDDEN.name)

    def test_admin_recommendation_job_run_bad_request_when_job_type_missing(self) -> None:
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.url, data={}, format="json")

        self.assertEqual(response.status_code, 400)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["code"], ErrorMessages.JOB_TYPE_MISSING.name)

    def test_admin_recommendation_job_run_conflict_when_pending_exists(self) -> None:
        RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=None,
            status=RecommendationJob.Status.PENDING,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.url, data={"job_type": "user_refresh"}, format="json")

        self.assertEqual(response.status_code, 409)
        data = cast(dict[str, Any], response.data)
        self.assertEqual(data["code"], ErrorMessages.JOB_ALREADY_RUNNING.name)

    def test_admin_recommendation_job_run_success(self) -> None:
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            self.url,
            data={"job_type": "user_refresh", "target_user": None},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(payload["type"], RecommendationJob.JobType.USER_REFRESH)
        self.assertEqual(payload["status"], RecommendationJob.Status.PENDING)
        self.assertIsNotNone(payload["created_at"])

    def test_admin_recommendation_job_run_enqueues_when_target_user_exists(self) -> None:
        target_user = User.objects.create_user(
            email="target-run@ex.com",
            nickname="target-run",
            birth_date=date(1995, 1, 1),
            password="pw",
        )
        self.client.force_authenticate(user=self.admin_user)

        with patch("apps.recommendations.views_admin.process_user_refresh_job.delay") as mocked_delay:
            response = self.client.post(
                self.url,
                data={"job_type": "user_refresh", "target_user": target_user.id},
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        job_id = cast(dict[str, Any], response.data)["id"]
        mocked_delay.assert_called_once_with(job_id)

    def test_admin_recommendation_job_run_similarity_rebuild_rejects_target_user(self) -> None:
        target_user = User.objects.create_user(
            email="target-run2@ex.com",
            nickname="target-run2",
            birth_date=date(1996, 1, 1),
            password="pw",
        )
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            self.url,
            data={"job_type": "similarity_rebuild", "target_user": target_user.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_admin_recommendation_job_run_similarity_rebuild_enqueues(self) -> None:
        self.client.force_authenticate(user=self.admin_user)

        with patch("apps.recommendations.views_admin.process_similarity_rebuild_job.delay") as mocked_delay:
            response = self.client.post(
                self.url,
                data={"job_type": "similarity_rebuild"},
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(payload["type"], RecommendationJob.JobType.SIMILARITY_REBUILD)
        mocked_delay.assert_called_once_with(payload["id"])
