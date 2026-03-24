from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from math import sqrt

from celery import shared_task
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.games.igdb import cache as igdb_cache
from apps.interactions.models import InteractionLog
from apps.recommendations.models import GameSimilarity, RecommendationJob, UserRecommendation
from apps.users.models import User

MAX_SEED_GAMES = 20
MAX_RECENT_LOG_SCAN = 200
MAX_RECOMMENDATIONS = 50
RECOMMENDATION_EXPIRE_DAYS = 7
MAX_SIMILAR_PER_GAME = 50


def _collect_preference_seed_game_ids(*, user_id: int) -> list[int]:
    """선호 장르/플랫폼/태그 기반으로 인기 게임 ID를 seed로 수집 (신규 유저 fallback)"""
    from apps.preferences.models import UserPreference

    try:
        pref = UserPreference.objects.get(user_id=user_id)
    except UserPreference.DoesNotExist:
        return []

    genre_ids = list(pref.userpreferencegenre_set.values_list("genre_id", flat=True))
    platform_ids = list(pref.userpreferenceplatform_set.values_list("platform_id", flat=True))
    tag_ids = list(pref.userpreferencetag_set.values_list("tag_id", flat=True))

    if not genre_ids and not platform_ids and not tag_ids:
        return []

    games = igdb_cache.search_games(
        genre_ids=genre_ids or None,
        platform_ids=platform_ids or None,
        tag_ids=tag_ids or None,
        sort="rating desc",
        limit=MAX_SEED_GAMES,
    )
    return [g["id"] for g in games]


def _collect_seed_game_ids(*, user_id: int) -> list[int]:
    recent_game_ids = list(
        InteractionLog.objects.filter(user_id=user_id, igdb_game_id__isnull=False)
        .order_by("-created_at")
        .values_list("igdb_game_id", flat=True)[:MAX_RECENT_LOG_SCAN]
    )
    unique_seed_game_ids: list[int] = [gid for gid in dict.fromkeys(recent_game_ids) if gid is not None]
    seed_game_ids = unique_seed_game_ids[:MAX_SEED_GAMES]

    if not seed_game_ids:
        seed_game_ids = _collect_preference_seed_game_ids(user_id=user_id)

    return seed_game_ids


def _build_similarity_candidates(*, seed_game_ids: list[int]) -> list[tuple[int, Decimal]]:
    if not seed_game_ids:
        return []

    similarity_qs = GameSimilarity.objects.filter(igdb_game_id__in=seed_game_ids).exclude(
        igdb_similar_game_id__in=seed_game_ids
    )

    rows = (
        similarity_qs.values("igdb_similar_game_id")
        .annotate(score=Max("score"))
        .order_by("-score")[:MAX_RECOMMENDATIONS]
    )
    return [(row["igdb_similar_game_id"], row["score"]) for row in rows]


def _upsert_recommendations(
    *,
    user_id: int,
    generation_version: int,
    candidates: list[tuple[int, Decimal]],
) -> None:
    now = timezone.now()
    expires_at = now + timedelta(days=RECOMMENDATION_EXPIRE_DAYS)

    for rank, (igdb_game_id, score) in enumerate(candidates, start=1):
        UserRecommendation.objects.update_or_create(
            user_id=user_id,
            igdb_game_id=igdb_game_id,
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


def _build_similarity_pairs_from_interactions() -> dict[tuple[int, int], Decimal]:
    # 대량 InteractionLog를 한 번에 메모리에 올리지 않기 위해 iterator로 스트리밍 처리합니다.
    user_rows_iterator = (
        InteractionLog.objects.filter(igdb_game_id__isnull=False).values_list("user_id", "igdb_game_id")
    ).iterator()
    user_games: defaultdict[int, set[int]] = defaultdict(set)
    for user_id, game_id in user_rows_iterator:
        # mypy 관점에서는 values_list가 Optional을 반환할 수 있어 타입 가드를 추가합니다.
        if game_id is None:
            continue
        user_games[user_id].add(int(game_id))

    game_user_count: defaultdict[int, int] = defaultdict(int)
    co_occurrence: defaultdict[tuple[int, int], int] = defaultdict(int)

    for games in user_games.values():
        game_ids = sorted(games)
        for game_id in game_ids:
            game_user_count[game_id] += 1
        for idx, game_id in enumerate(game_ids):
            for similar_game_id in game_ids[idx + 1 :]:
                co_occurrence[(game_id, similar_game_id)] += 1

    pair_scores: dict[tuple[int, int], Decimal] = {}
    for (a, b), overlap in co_occurrence.items():
        denominator = sqrt(game_user_count[a] * game_user_count[b])
        if denominator == 0:
            continue
        score = Decimal(str(overlap / denominator)).quantize(Decimal("0.0001"))
        if score <= 0:
            continue
        pair_scores[(a, b)] = score
        pair_scores[(b, a)] = score

    return pair_scores


def _replace_game_similarities(*, pair_scores: dict[tuple[int, int], Decimal]) -> int:
    top_per_game: defaultdict[int, list[tuple[int, Decimal]]] = defaultdict(list)
    for (game_id, similar_game_id), score in pair_scores.items():
        top_per_game[game_id].append((similar_game_id, score))

    records: list[GameSimilarity] = []
    for game_id, similars in top_per_game.items():
        ranked_similars = sorted(similars, key=lambda item: item[1], reverse=True)[:MAX_SIMILAR_PER_GAME]
        for similar_game_id, score in ranked_similars:
            records.append(
                GameSimilarity(
                    igdb_game_id=game_id,
                    igdb_similar_game_id=similar_game_id,
                    score=score,
                )
            )

    with transaction.atomic():
        GameSimilarity.objects.all().delete()
        if records:
            GameSimilarity.objects.bulk_create(records, batch_size=1000)

    return len(records)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_user_refresh_job(self, job_id: int) -> None:  # type: ignore[no-untyped-def]
    run_user_refresh_job(job_id)


def run_user_refresh_job(job_id: int) -> None:
    target_user_id: int | None = None
    current_retry_count = 0
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
        if job.status == RecommendationJob.Status.PENDING:
            pass
        elif job.status == RecommendationJob.Status.RUNNING and job.started_at is None:
            pass
        else:
            return
        target_user_id = job.target_user_id
        current_retry_count = job.retry_count

        job.status = RecommendationJob.Status.RUNNING
        job.started_at = timezone.now()
        job.error_message = None
        job.save(update_fields=["status", "started_at", "error_message"])

    try:
        if target_user_id is None:
            return
        user = User.objects.get(id=target_user_id)
        seed_game_ids = _collect_seed_game_ids(user_id=user.id)
        candidates = _build_similarity_candidates(seed_game_ids=seed_game_ids)

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
            retry_count=current_retry_count + 1,
            error_message=str(err)[:1000],
        )
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_similarity_rebuild_job(self, job_id: int) -> None:  # type: ignore[no-untyped-def]
    run_similarity_rebuild_job(job_id)


def run_similarity_rebuild_job(job_id: int) -> None:
    current_retry_count = 0
    with transaction.atomic():
        job = (
            RecommendationJob.objects.select_for_update()
            .filter(
                id=job_id,
                job_type=RecommendationJob.JobType.SIMILARITY_REBUILD,
            )
            .first()
        )
        if job is None:
            return
        if job.status == RecommendationJob.Status.PENDING:
            pass
        elif job.status == RecommendationJob.Status.RUNNING and job.started_at is None:
            pass
        else:
            return
        current_retry_count = job.retry_count

        job.status = RecommendationJob.Status.RUNNING
        job.started_at = timezone.now()
        job.error_message = None
        job.save(update_fields=["status", "started_at", "error_message"])

    try:
        pair_scores = _build_similarity_pairs_from_interactions()
        _replace_game_similarities(pair_scores=pair_scores)
        RecommendationJob.objects.filter(id=job_id).update(
            status=RecommendationJob.Status.SUCCESS,
            finished_at=timezone.now(),
        )
    except Exception as err:
        RecommendationJob.objects.filter(id=job_id).update(
            status=RecommendationJob.Status.FAILED,
            finished_at=timezone.now(),
            retry_count=current_retry_count + 1,
            error_message=str(err)[:1000],
        )
        raise


@shared_task
def process_pending_recommendation_jobs(limit: int = 20) -> int:
    with transaction.atomic():
        pending_user_refresh_job_ids = list(
            RecommendationJob.objects.select_for_update(skip_locked=True)
            .filter(
                job_type=RecommendationJob.JobType.USER_REFRESH,
                status=RecommendationJob.Status.PENDING,
                target_user_id__isnull=False,
            )
            .order_by("created_at")
            .values_list("id", flat=True)[:limit]
        )

        if pending_user_refresh_job_ids:
            RecommendationJob.objects.filter(
                id__in=pending_user_refresh_job_ids,
                status=RecommendationJob.Status.PENDING,
            ).update(
                status=RecommendationJob.Status.RUNNING,
                started_at=None,
            )

    remaining_limit = max(limit - len(pending_user_refresh_job_ids), 0)
    pending_similarity_rebuild_job_ids: list[int] = []
    if remaining_limit > 0:
        with transaction.atomic():
            pending_similarity_rebuild_job_ids = list(
                RecommendationJob.objects.select_for_update(skip_locked=True)
                .filter(
                    job_type=RecommendationJob.JobType.SIMILARITY_REBUILD,
                    status=RecommendationJob.Status.PENDING,
                )
                .order_by("created_at")
                .values_list("id", flat=True)[:remaining_limit]
            )
            if pending_similarity_rebuild_job_ids:
                RecommendationJob.objects.filter(
                    id__in=pending_similarity_rebuild_job_ids,
                    status=RecommendationJob.Status.PENDING,
                ).update(
                    status=RecommendationJob.Status.RUNNING,
                    started_at=None,
                )

    for job_id in pending_user_refresh_job_ids:
        process_user_refresh_job.delay(job_id)
    for job_id in pending_similarity_rebuild_job_ids:
        process_similarity_rebuild_job.delay(job_id)

    return len(pending_user_refresh_job_ids) + len(pending_similarity_rebuild_job_ids)
