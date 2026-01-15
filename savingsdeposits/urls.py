from django.urls import path

from savingsdeposits.views import (
    SavingsDepositListCreateView,
    SavingsDepositView,
    BulkSavingsDepositView,
    BulkSavingsDepositUploadView,
    MpesaSavingsDepositView,
    MpesaSavingsDepositCallbackView,
)

app_name = "savingsdeposits"

urlpatterns = [
    path("", SavingsDepositListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", SavingsDepositView.as_view(), name="detail"),
    path("bulk/", BulkSavingsDepositView.as_view(), name="bulk-create"),
    path("bulk/upload/", BulkSavingsDepositUploadView.as_view(), name="bulk-upload"),
    path("mpesa/pay/", MpesaSavingsDepositView.as_view(), name="mpesa"),
    path(
        "mpesa/callback/",
        MpesaSavingsDepositCallbackView.as_view(),
        name="mpesa-callback",
    ),
]
