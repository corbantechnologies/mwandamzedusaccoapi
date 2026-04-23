from django.urls import path

from loanpayments.views import (
    LoanPaymentCreateView,
    LoanPaymentDetailView,
    LoanMpesaPaymentListCreateView,
)

urlpatterns = [
    path("", LoanPaymentCreateView.as_view(), name="loan_payment_create"),
    path(
        "<str:reference>/", LoanPaymentDetailView.as_view(), name="loan_payment_detail"
    ),
    path(
        "list/mpesa/payment/",
        LoanMpesaPaymentListCreateView.as_view(),
        name="loan_mpesa_payment",
    ),
]
