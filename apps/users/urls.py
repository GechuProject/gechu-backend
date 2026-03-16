from django.urls import path

from apps.users.views.adult_verification import (
    AdultVerificationCallbackAPIView,
    AdultVerificationInitiateAPIView,
    AdultVerificationStatusAPIView,
)
from apps.users.views.auth import (
    AccountRestoreAPIView,
    AuthMeAPIView,
    EmailCodeSendAPIView,
    LoginAPIView,
    LogoutAPIView,
    PasswordResetAPIView,
    RefreshAPIView,
    SignupAPIView,
)
from apps.users.views.me import UserMeAPIView, UserPasswordChangeAPIView, UserPasswordVerifyAPIView
from apps.users.views.social_auth import (
    KakaoCallbackAPIView,
    KakaoLoginAPIView,
)

urlpatterns = [
    path("auth/signup/", SignupAPIView.as_view(), name="auth-signup"),
    path("auth/email/code/", EmailCodeSendAPIView.as_view(), name="auth-email-code"),
    path("auth/login/", LoginAPIView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutAPIView.as_view(), name="auth-logout"),
    path("auth/restore/", AccountRestoreAPIView.as_view(), name="auth-restore"),
    path("auth/refresh/", RefreshAPIView.as_view(), name="auth-refresh"),
    path("auth/password/reset/", PasswordResetAPIView.as_view(), name="auth-password-reset"),
    path("auth/me/", AuthMeAPIView.as_view(), name="auth-me"),
    path("users/me/", UserMeAPIView.as_view(), name="users-me"),
    path("users/me/verify-password/", UserPasswordVerifyAPIView.as_view(), name="users-me-verify-password"),
    path("users/me/password/", UserPasswordChangeAPIView.as_view(), name="users-me-password-change"),
    path("auth/kakao/login/", KakaoLoginAPIView.as_view(), name="auth-kakao-login"),
    path("auth/kakao/callback/", KakaoCallbackAPIView.as_view(), name="auth-kakao-callback"),
    path(
        "users/me/adult-verifications/initiate/",
        AdultVerificationInitiateAPIView.as_view(),
        name="users-me-adult-verifications-initiate",
    ),
    path(
        "users/me/adult-verifications/callback/",
        AdultVerificationCallbackAPIView.as_view(),
        name="users-me-adult-verifications-callback",
    ),
    path(
        "users/me/adult-verifications/",
        AdultVerificationStatusAPIView.as_view(),
        name="users-me-adult-verifications",
    ),
]
