from django.urls import URLPattern, URLResolver, path

from apps.games.igdb.views import IgdbSyncView
from apps.games.views.rawg_sync import RawgSyncView

urlpatterns: list[URLPattern | URLResolver] = [
    path("sync/rawg/", RawgSyncView.as_view(), name="admin-rawg-sync"),
    path("sync/igdb", IgdbSyncView.as_view(), name="admin-igdb-sync"),
]
