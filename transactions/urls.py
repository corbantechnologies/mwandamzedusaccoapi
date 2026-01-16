from django.urls import path

from transactions.views import (
    AccountListView,
    AccountDetailView,
    AccountListDownloadView,
    CombinedBulkUploadView,
    MemberYearlySummaryView,
    MemberYearlySummaryPDFView,
)

urlpatterns = [
    path("", AccountListView.as_view(), name="account-list"),
    path(
        "summary/yearly/<str:member_no>/",
        MemberYearlySummaryView.as_view(),
        name="member-yearly-summary",
    ),
    path(
        "summary/yearly/<str:member_no>/pdf/",
        MemberYearlySummaryPDFView.as_view(),
        name="member-yearly-summary-pdf",
    ),
    path("<str:member_no>/", AccountDetailView.as_view(), name="account-detail"),
    path(
        "list/download/",
        AccountListDownloadView.as_view(),
        name="account-list-download",
    ),
    path(
        "bulk/upload/",
        CombinedBulkUploadView.as_view(),
        name="combined-bulk-upload",
    ),
]
