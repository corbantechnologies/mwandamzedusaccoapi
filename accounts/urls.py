from django.urls import path

from accounts.views import (
    TokenView,
    UserDetailView,
    MemberListView,
    MemberDetailView,
    ActivateAccountView,
    PasswordChangeView,
    MemberCreatedByAdminView,
    ForgotPasswordView,
    ResetPasswordView,
)

app_name = "accounts"

urlpatterns = [
    path("token/", TokenView.as_view(), name="token"),
    path("<str:id>/", UserDetailView.as_view(), name="user-detail"),
    # System admin activities
    path("", MemberListView.as_view(), name="members"),
    path("member/<str:member_no>/", MemberDetailView.as_view(), name="member-detail"),
    path(
        "new-member/create/",
        MemberCreatedByAdminView.as_view(),
        name="member-created-by-admin",
    ),
    # Password Reset
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("password/forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("password/reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    # Account activation
    path(
        "password/activate-account/",
        ActivateAccountView.as_view(),
        name="activate-account",
    ),
]
