from typing import Any

from apps.games.models import Genre


class GenreService:
    @staticmethod
    def get_all_genres() -> list[dict[str, Any]]:
        return list(Genre.objects.values("id", "name", "slug").order_by("id"))  # type: ignore[arg-type]
