from django.urls import path

from feepayments.views import (
    FeePaymentListCreateView,
    FeePaymentView,
    BulkFeePaymentUploadView,
    BulkFeePaymentCreateView,
    FeePaymentTemplateDownloadView,
)

urlpatterns = [
    path("", FeePaymentListCreateView.as_view(), name="fee-payment-list"),
    path(
        "bulk/template/",
        FeePaymentTemplateDownloadView.as_view(),
        name="fee-payment-bulk-template",
    ),
    path(
        "bulk/upload/",
        BulkFeePaymentUploadView.as_view(),
        name="fee-payment-bulk-upload",
    ),
    path(
        "bulk/create/",
        BulkFeePaymentCreateView.as_view(),
        name="fee-payment-bulk-create",
    ),
    path("<str:reference>/", FeePaymentView.as_view(), name="fee-payment-detail"),
]
