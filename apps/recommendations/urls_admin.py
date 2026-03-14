from django.urls import path

from apps.recommendations.views_admin import AdminRecommendationJobListView

urlpatterns = [
    path("", AdminRecommendationJobListView.as_view(), name="admin-recommendation-job-list"),
]
