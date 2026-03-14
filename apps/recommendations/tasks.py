from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.games.models import Game
from apps.interactions.models import InteractionLog
from apps.recommendations.models import GameSimilarity, RecommendationJob, UserRecommendation

MAX_SEED_GAMES = 20
MAX_RECENT_LOG_SCAN = 200
MAX_RECOMMENDATIONS = 50
RECOMMENDATION_EXPIRE_DAYS = 7


def _collect_seed_game_ids(*, user_id: int) -> list[int]:
    recent_game_ids = list(
        InteractionLog.objects.filter(user_id=user_id, game_id__isnull=False)
        .order_by("-created_at")
        .values_list("game_id", flat=True)[:MAX_RECENT_LOG_SCAN]
    )
    unique_seed_game_ids = list(dict.fromkeys(recent_game_ids))
    return unique_seed_game_ids[:MAX_SEED_GAMES]


def _build_similarity_candidates(*, seed_game_ids: list[int], is_adult_verified: bool) -> list[tuple[int, Decimal]]:
    if not seed_game_ids:
        return []

    similarity_qs = GameSimilarity.objects.filter(
        game_id__in=seed_game_ids,
        similar_game__is_visible=True,
    ).exclude(similar_game_id__in=seed_game_ids)

    if not is_adult_verified:
        similarity_qs = similarity_qs.filter(similar_game__age_rating_min__lt=18)

    rows = similarity_qs.values("similar_game_id").annotate(score=Max("score")).order_by("-score")[:MAX_RECOMMENDATIONS]
    return [(row["similar_game_id"], row["score"]) for row in rows]


def _build_fallback_candidates(*, is_adult_verified: bool) -> list[tuple[int, Decimal]]:
    fallback_qs = Game.objects.filter(is_visible=True)
    if not is_adult_verified:
        fallback_qs = fallback_qs.filter(age_rating_min__lt=18)

    rows = fallback_qs.order_by("-rawg_rating")[:MAX_RECOMMENDATIONS].values("id", "rawg_rating")
    return [(row["id"], (row["rawg_rating"] / Decimal("5")).quantize(Decimal("0.0001"))) for row in rows]


def _upsert_recommendations(
    *,
    user_id: int,
    generation_version: int,
    candidates: list[tuple[int, Decimal]],
) -> None:
    now = timezone.now()
    expires_at = now + timedelta(days=RECOMMENDATION_EXPIRE_DAYS)

    for rank, (game_id, score) in enumerate(candidates, start=1):
        UserRecommendation.objects.update_or_create(
            user_id=user_id,
            game_id=game_id,
            defaults={
                "generation_version": generation_version,
                "score": score,
                "rank": rank,
                "reason": UserRecommendation.ReasonType.SIMILARITY,
                "generated_at": now,
                "expires_at": expires_at,
            },
        )

    UserRecommendation.objects.filter(user_id=user_id).exclude(generation_version=generation_version).delete()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_user_refresh_job(self, job_id: int) -> None:  # type: ignore[no-untyped-def]
    with transaction.atomic():
        job = (
            RecommendationJob.objects.select_for_update()
            .filter(
                id=job_id,
                job_type=RecommendationJob.JobType.USER_REFRESH,
            )
            .first()
        )
        if job is None or job.target_user_id is None:
            return
        if job.status not in {RecommendationJob.Status.PENDING, RecommendationJob.Status.RUNNING}:
            return

        job.status = RecommendationJob.Status.RUNNING
        job.started_at = timezone.now()
        job.error_message = None
        job.save(update_fields=["status", "started_at", "error_message"])

    try:
        user = job.target_user
        seed_game_ids = _collect_seed_game_ids(user_id=user.id)
        candidates = _build_similarity_candidates(seed_game_ids=seed_game_ids, is_adult_verified=user.is_adult_verified)
        if not candidates:
            candidates = _build_fallback_candidates(is_adult_verified=user.is_adult_verified)

        latest_generation = (
            UserRecommendation.objects.filter(user_id=user.id).aggregate(max_generation=Max("generation_version"))[
                "max_generation"
            ]
            or 0
        )
        next_generation = latest_generation + 1
        _upsert_recommendations(
            user_id=user.id,
            generation_version=next_generation,
            candidates=candidates,
        )

        RecommendationJob.objects.filter(id=job_id).update(
            status=RecommendationJob.Status.SUCCESS,
            finished_at=timezone.now(),
        )
    except Exception as err:
        RecommendationJob.objects.filter(id=job_id).update(
            status=RecommendationJob.Status.FAILED,
            finished_at=timezone.now(),
            retry_count=job.retry_count + 1,
            error_message=str(err)[:1000],
        )
        raise


@shared_task
def process_pending_recommendation_jobs(limit: int = 20) -> int:
    pending_job_ids = list(
        RecommendationJob.objects.filter(
            job_type=RecommendationJob.JobType.USER_REFRESH,
            status=RecommendationJob.Status.PENDING,
            target_user_id__isnull=False,
        )
        .order_by("created_at")
        .values_list("id", flat=True)[:limit]
    )
    for job_id in pending_job_ids:
        process_user_refresh_job.delay(job_id)
    return len(pending_job_ids)
