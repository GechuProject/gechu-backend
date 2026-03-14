from django.urls import path

from apps.recommendations.views import RecommendationListView, RecommendationStatusView

urlpatterns = [
    path("", RecommendationListView.as_view(), name="recommendation-list"),
    path("status/", RecommendationStatusView.as_view(), name="recommendation-status"),
]
