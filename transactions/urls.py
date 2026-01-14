from django.urls import path

from transactions.views import (
    AccountListView,
    AccountDetailView,
    AccountListDownloadView,
    CombinedBulkUploadView,
)

urlpatterns = [
    path("", AccountListView.as_view(), name="account-list"),
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
