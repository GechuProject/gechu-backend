from django.db import models


# 장르
class Genre(models.Model):
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


# 플랫폼
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


# 태그
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
