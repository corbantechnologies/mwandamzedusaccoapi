from django.urls import path

from loanpayments.views import LoanPaymentCreateView, LoanPaymentDetailView

urlpatterns = [
    path("", LoanPaymentCreateView.as_view(), name="loan_payment_create"),
    path(
        "<str:reference>/", LoanPaymentDetailView.as_view(), name="loan_payment_detail"
    ),
]
