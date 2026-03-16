from django.urls import path

from apps.recommendations.views_admin import AdminRecommendationJobDetailView, AdminRecommendationJobListView

urlpatterns = [
    path("", AdminRecommendationJobListView.as_view(), name="admin-recommendation-job-list"),
    path("<int:job_id>/", AdminRecommendationJobDetailView.as_view(), name="admin-recommendation-job-detail"),
]
