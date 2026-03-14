from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from django.db.models import QuerySet

from apps.recommendations.models import RecommendationJob, UserRecommendation
from apps.users.models import User


class RecommendationStatusResult(TypedDict):
    status: str
    generation: int | None
    generated_at: datetime | None
    expires_at: datetime | None


class RecommendationStatusService:
    @staticmethod
    def get_status(*, user: User) -> RecommendationStatusResult:
        latest_job = RecommendationService._get_latest_user_refresh_job(user=user)
        latest_recommendation = (
            UserRecommendation.objects.filter(user=user)
            .order_by("-generation_version", "-generated_at")
            .first()
        )

        has_recommendation = latest_recommendation is not None

        if latest_job is None:
            status = "success" if has_recommendation else "pending"
        elif latest_job.status in (RecommendationJob.Status.PENDING, RecommendationJob.Status.RUNNING):
            status = "pending"
        elif latest_job.status == RecommendationJob.Status.FAILED:
            status = "failed"
        elif latest_job.status == RecommendationJob.Status.SUCCESS:
            status = "success" if has_recommendation else "pending"
        else:
            status = "pending"

        return {
            "status": status,
            "generation": latest_recommendation.generation_version if latest_recommendation else None,
            "generated_at": latest_recommendation.generated_at if latest_recommendation else None,
            "expires_at": latest_recommendation.expires_at if latest_recommendation else None,
        }


class RecommendationService:
    @staticmethod
    def _get_latest_user_refresh_job(*, user: User) -> RecommendationJob | None:
        return (
            RecommendationJob.objects.filter(
                target_user=user,
                job_type=RecommendationJob.JobType.USER_REFRESH,
            )
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def is_recommendation_ready(*, user: User) -> bool:
        latest_user_refresh_job = RecommendationService._get_latest_user_refresh_job(user=user)
        if latest_user_refresh_job is not None and latest_user_refresh_job.status in {
            RecommendationJob.Status.PENDING,
            RecommendationJob.Status.RUNNING,
        }:
            return False

        has_visible_recommendation = UserRecommendation.objects.filter(user=user, game__is_visible=True).exists()
        return has_visible_recommendation

    @staticmethod
    def list_recommendations(
        *,
        user: User,
        rec_type: str | None = None,
        genre_ids: list[int] | None = None,
        tag_ids: list[int] | None = None,
        is_adult: bool | None = None,
        is_free: bool | None = None,
    ) -> QuerySet[UserRecommendation]:
        qs = (
            UserRecommendation.objects.filter(user=user, game__is_visible=True)
            .select_related("game")
            .prefetch_related("game__game_genres__genre", "game__game_tags__tag")
        )

        if rec_type:
            qs = qs.filter(reason=rec_type)
        if genre_ids:
            qs = qs.filter(game__game_genres__genre_id__in=genre_ids)
        if tag_ids:
            qs = qs.filter(game__game_tags__tag_id__in=tag_ids)
        if is_adult is True:
            qs = qs.filter(game__age_rating_min__gte=18)
        elif is_adult is False:
            qs = qs.filter(game__age_rating_min__lt=18)

        if is_free is not None:
            pass

        return qs.distinct().order_by("rank")

    @staticmethod
    def enqueue_user_refresh_job_if_needed(*, user: User) -> RecommendationJob:
        latest_user_refresh_job = RecommendationService._get_latest_user_refresh_job(user=user)
        if latest_user_refresh_job is not None and latest_user_refresh_job.status in {
            RecommendationJob.Status.PENDING,
            RecommendationJob.Status.RUNNING,
        }:
            return latest_user_refresh_job

        return RecommendationJob.objects.create(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            target_user=user,
            status=RecommendationJob.Status.PENDING,
        )
