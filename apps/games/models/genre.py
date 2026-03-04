from django.db import models

from apps.core.models import TimeStampedModel


class Genre(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    rawg_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=50)
    slug = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "genres"
        verbose_name = "장르"
        verbose_name_plural = "장르들"

    def __str__(self) -> str:
        return self.name
