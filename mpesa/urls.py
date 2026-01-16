from django.urls import path
from mpesa.views import MpesaPaymentCreateView, MpesaCallbackView

app_name = "mpesa"

urlpatterns = [
    path("pay/", MpesaPaymentCreateView.as_view(), name="payment"),
    path("callback/", MpesaCallbackView.as_view(), name="callback"),
]
