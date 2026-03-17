from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from django.db.models import QuerySet

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.recommendations.models import RecommendationJob, UserRecommendation
from apps.users.models import User


class RecommendationStatusResult(TypedDict):
    status: str
    generation_version: int | None
    generated_at: datetime | None
    expires_at: datetime | None


class RecommendationStatusService:
    @staticmethod
    def get_status(*, user: User) -> RecommendationStatusResult:
        latest_job = RecommendationService.get_latest_user_refresh_job(user=user)
        latest_recommendation = (
            UserRecommendation.objects.filter(user=user).order_by("-generation_version", "-generated_at").first()
        )

        has_recommendation = latest_recommendation is not None

        if latest_job is None or latest_job.status == RecommendationJob.Status.SUCCESS:
            status = "success" if has_recommendation else "pending"
        elif latest_job.status == RecommendationJob.Status.PENDING:
            status = "pending"
        elif latest_job.status == RecommendationJob.Status.RUNNING:
            status = "running"
        elif latest_job.status == RecommendationJob.Status.FAILED:
            status = "failed"
        else:
            status = "pending"

        return {
            "status": status,
            "generation_version": latest_recommendation.generation_version if latest_recommendation else None,
            "generated_at": latest_recommendation.generated_at if latest_recommendation else None,
            "expires_at": latest_recommendation.expires_at if latest_recommendation else None,
        }


class RecommendationService:
    @staticmethod
    def get_latest_user_refresh_job(*, user: User) -> RecommendationJob | None:
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
        latest_user_refresh_job = RecommendationService.get_latest_user_refresh_job(user=user)
        if latest_user_refresh_job is not None and latest_user_refresh_job.status in {
            RecommendationJob.Status.PENDING,
            RecommendationJob.Status.RUNNING,
        }:
            return False

        return UserRecommendation.objects.filter(user=user).exists()

    @staticmethod
    def list_recommendations(
        *,
        user: User,
        rec_type: str | None = None,
    ) -> QuerySet[UserRecommendation]:
        qs = UserRecommendation.objects.filter(user=user)

        if rec_type:
            qs = qs.filter(reason=rec_type)

        return qs.order_by("rank")

    @staticmethod
    def enqueue_user_refresh_job_if_needed(*, user: User) -> RecommendationJob:
        latest_user_refresh_job = RecommendationService.get_latest_user_refresh_job(user=user)
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


class RecommendationAdminService:
    @staticmethod
    def list_recommendation_jobs(
        *,
        job_status: str | None = None,
        job_type: str | None = None,
    ) -> QuerySet[RecommendationJob]:
        qs = RecommendationJob.objects.select_related("target_user").all()

        if job_status:
            qs = qs.filter(status=job_status)
        if job_type:
            qs = qs.filter(job_type=job_type)

        return qs.order_by("-created_at")

    @staticmethod
    def get_recommendation_job(*, job_id: int) -> RecommendationJob | None:
        return RecommendationJob.objects.select_related("target_user").filter(id=job_id).first()

    @staticmethod
    def create_recommendation_job(
        *,
        job_type: str,
        target_user_id: int | None,
    ) -> RecommendationJob:
        has_running_job = RecommendationJob.objects.filter(
            job_type=job_type,
            target_user_id=target_user_id,
            status__in=[RecommendationJob.Status.PENDING, RecommendationJob.Status.RUNNING],
        ).exists()
        if has_running_job:
            raise CustomAPIException(ErrorMessages.JOB_ALREADY_RUNNING)

        return RecommendationJob.objects.create(
            job_type=job_type,
            target_user_id=target_user_id,
            status=RecommendationJob.Status.PENDING,
        )
