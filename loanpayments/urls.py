from django.urls import path

from loanpayments.views import (
    LoanPaymentCreateView,
    LoanPaymentDetailView,
    LoanMpesaPaymentListCreateView,
    LoanRepaymentTemplateDownloadView,
    BulkLoanRepaymentUploadView,
    BulkLoanRepaymentCreateView,
)

urlpatterns = [
    path("", LoanPaymentCreateView.as_view(), name="loan_payment_create"),
    path(
        "bulk/template/",
        LoanRepaymentTemplateDownloadView.as_view(),
        name="loan-payments-bulk-template",
    ),
    path(
        "bulk/upload/",
        BulkLoanRepaymentUploadView.as_view(),
        name="loan-payments-bulk-upload",
    ),
    path(
        "bulk/create/",
        BulkLoanRepaymentCreateView.as_view(),
        name="loan-payments-bulk-create",
    ),
    path(
        "<str:reference>/", LoanPaymentDetailView.as_view(), name="loan_payment_detail"
    ),
    path(
        "list/mpesa/payment/",
        LoanMpesaPaymentListCreateView.as_view(),
        name="loan_mpesa_payment",
    ),
]
