from django.db import models


class Tag(models.Model):
    id = models.BigAutoField(primary_key=True)
    rawg_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "tags"
        verbose_name = "태그"
        verbose_name_plural = "태그들"

    def __str__(self) -> str:
        return self.name
