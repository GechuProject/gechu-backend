from django.urls import path

from apps.recommendations.views_admin import (
    AdminRecommendationJobDetailView,
    AdminRecommendationJobListView,
    AdminRecommendationJobRunView,
)

urlpatterns = [
    path("", AdminRecommendationJobListView.as_view(), name="admin-recommendation-job-list"),
    path("run/", AdminRecommendationJobRunView.as_view(), name="admin-recommendation-job-run"),
    path("<int:job_id>/", AdminRecommendationJobDetailView.as_view(), name="admin-recommendation-job-detail"),
]
