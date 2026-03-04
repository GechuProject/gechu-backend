from django.urls import path
from .views.auth import EmailCodeSendAPIView

urlpatterns = [
    path("auth/email/code", EmailCodeSendAPIView.as_view(), name="auth-email-code"),
]