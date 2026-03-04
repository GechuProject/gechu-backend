from django.db import models


class Platform(models.Model):
    id = models.BigAutoField(primary_key=True)
    rawg_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=50)
    slug = models.CharField(max_length=50, unique=True)
    icon_url = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "platforms"
        verbose_name = "플랫폼"
        verbose_name_plural = "플랫폼들"

    def __str__(self) -> str:
        return self.name
