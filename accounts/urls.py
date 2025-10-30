from django.urls import path

from accounts.views import (
    TokenView,
    UserDetailView,
    MemberListView,
    MemberDetailView,
    ActivateAccountView,
    PasswordChangeView,
    MemberCreatedByAdminView,
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
    # Account activation
    path(
        "password/activate-account/",
        ActivateAccountView.as_view(),
        name="activate-account",
    ),
]
