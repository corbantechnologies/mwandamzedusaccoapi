from django.urls import path

from loandisbursements.views import (
    LoanDisbursementListCreateView,
    LoanDisbursementDetailView,
    BulkLoanDisbursementUploadView,
    BulkLoanDisbursementCreateView,
    LoanDisbursementTemplateDownloadView,
)

app_name = "loandisbursements"

urlpatterns = [
    path("", LoanDisbursementListCreateView.as_view(), name="list-create"),
    path(
        "bulk/template/",
        LoanDisbursementTemplateDownloadView.as_view(),
        name="bulk-template",
    ),
    path("bulk/upload/", BulkLoanDisbursementUploadView.as_view(), name="bulk-upload"),
    path("bulk/create/", BulkLoanDisbursementCreateView.as_view(), name="bulk-create"),
    path("<str:reference>/", LoanDisbursementDetailView.as_view(), name="detail"),
]
