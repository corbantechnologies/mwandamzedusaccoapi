from django.urls import path

from loanproducts.views import (
    LoanProductDetailView,
    LoanProductListCreateView,
    LoanProductTemplateDownloadView,
    BulkLoanProductUploadView,
    BulkLoanProductCreateView,
)

app_name = "loanproducts"

urlpatterns = [
    path("", LoanProductListCreateView.as_view(), name="loanproducts"),
    path(
        "bulk/template/",
        LoanProductTemplateDownloadView.as_view(),
        name="loanproducts-bulk-template",
    ),
    path(
        "bulk/upload/",
        BulkLoanProductUploadView.as_view(),
        name="loanproducts-bulk-upload",
    ),
    path(
        "bulk/create/",
        BulkLoanProductCreateView.as_view(),
        name="loanproducts-bulk-create",
    ),
    path(
        "<str:reference>/", LoanProductDetailView.as_view(), name="loanproduct-detail"
    ),
]
