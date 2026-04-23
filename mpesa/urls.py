from django.urls import path
from mpesa.views import (
    MpesaPaymentCreateView,
    MpesaCallbackView,
    LoanPaymentMpesaCreateView,
    LoanMpesaCallbackView,
)

app_name = "mpesa"

urlpatterns = [
    path("pay/", MpesaPaymentCreateView.as_view(), name="payment"),
    path("callback/", MpesaCallbackView.as_view(), name="callback"),
    path("pay/loan/member/", LoanPaymentMpesaCreateView.as_view(), name="loan_payment"),
    path("callback/loan/", LoanMpesaCallbackView.as_view(), name="loan_callback"),
]
