from django.db import models

class ExternalStore(models.Model):
    id = models.BigAutoField(primary_key=True)
    rawg_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=50)
    slug = models.CharField(max_length=50, unique=True)
    domain = models.CharField(max_length=100)
    icon_url = models.CharField(max_length=255, default="", blank=True)

    class Meta:
        db_table = "external_stores"

    def __str__(self) -> str:
        return self.name