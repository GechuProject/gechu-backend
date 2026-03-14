from django.urls import path

from apps.recommendations.views import RecommendationListView

urlpatterns = [
    path("", RecommendationListView.as_view(), name="recommendation-list"),
]
