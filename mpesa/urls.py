from django.urls import path
from savingsdeposits.views import (
    MpesaSavingsDepositView,
    MpesaSavingsDepositCallbackView,
)

app_name = "mpesa"

urlpatterns = [
    path("save", MpesaSavingsDepositView.as_view(), name="save"),
    path(
        "callback/",
        MpesaSavingsDepositCallbackView.as_view(),
        name="callback",
    ),
]
