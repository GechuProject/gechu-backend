from django.urls import path

from apps.users.views.auth import LoginAPIView, LogoutAPIView, SignupAPIView

from .views.auth import EmailCodeSendAPIView

urlpatterns = [
    path("auth/signup/", SignupAPIView.as_view(), name="auth-signup"),
    path("auth/email/code/", EmailCodeSendAPIView.as_view(), name="auth-email-code"),
    path("auth/login/", LoginAPIView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutAPIView.as_view(), name="auth-logout"),
]
