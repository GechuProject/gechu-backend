from django.urls import path
from .views.auth import EmailCodeSendAPIView, SignupAPIView

urlpatterns = [
    path("auth/email/code", EmailCodeSendAPIView.as_view(), name="auth-email-code"),
    path("auth/signup", SignupAPIView.as_view(), name="auth-signup"),
]