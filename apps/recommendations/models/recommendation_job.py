from django.db import models

from apps.core.models import TimeStampedModel


class RecommendationJob(TimeStampedModel):

    class JobType(models.TextChoices):
        USER_REFRESH = "user_refresh", "User Refresh"
        SIMILARITY_REBUILD = "similarity_rebuild", "Similarity Rebuild"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.BigAutoField(primary_key=True)

    job_type = models.CharField(
        max_length=30,
        choices=JobType.choices,
    )

    target_user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recommendation_jobs",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    retry_count = models.IntegerField(default=0)

    error_message = models.TextField(
        null=True,
        blank=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "recommendation_jobs"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["job_type"]),
            models.Index(fields=["target_user"]),
        ]

    def __str__(self) -> str:
        return f"{self.job_type} ({self.status})"