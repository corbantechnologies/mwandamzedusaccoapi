from django.urls import path

from paymentaccounts.views import (
    PaymentAccountListCreateView,
    PaymentAccountDetailView,
    PaymentAccountTemplateDownloadView,
    BulkPaymentAccountUploadView,
    BulkPaymentAccountCreateView,
)

urlpatterns = [
    path("", PaymentAccountListCreateView.as_view(), name="payment-accounts"),
    path(
        "bulk/template/",
        PaymentAccountTemplateDownloadView.as_view(),
        name="payment-account-bulk-template",
    ),
    path(
        "bulk/upload/",
        BulkPaymentAccountUploadView.as_view(),
        name="payment-account-bulk-upload",
    ),
    path(
        "bulk/create/",
        BulkPaymentAccountCreateView.as_view(),
        name="payment-account-bulk-create",
    ),
    path(
        "<str:reference>/", PaymentAccountDetailView.as_view(), name="payment-account"
    ),
]
