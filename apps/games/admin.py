from django.contrib import admin

from .models import Game


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "esrb_rating", "age_rating_min", "released")
    search_fields = ("name", "slug")
