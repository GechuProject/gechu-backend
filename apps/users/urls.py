from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views.jwt import EmailTokenObtainPairView

urlpatterns = [
    path("auth/login", EmailTokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="auth-refresh"),
]