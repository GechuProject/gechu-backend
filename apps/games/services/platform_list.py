from typing import Any

from apps.games.models import Platform


class PlatformService:
    @staticmethod
    def get_all_platforms() -> list[dict[str, Any]]:
        return list(Platform.objects.values("id", "name", "slug").order_by("id"))  # type: ignore[arg-type]
