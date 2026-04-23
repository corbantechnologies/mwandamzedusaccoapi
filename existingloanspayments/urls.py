from django.urls import path
from existingloanspayments import views

app_name = "existingloanspayments"

urlpatterns = [
    path(
        "",
        views.ExistingLoanPaymentCreateView.as_view(),
        name="existing-loan-payment-create",
    ),
    path(
        "bulk/template/",
        views.ExistingLoanPaymentTemplateDownloadView.as_view(),
        name="existing-loan-payment-bulk-template",
    ),
    path(
        "bulk/upload/",
        views.BulkExistingLoanPaymentUploadView.as_view(),
        name="existing-loan-payment-bulk-upload",
    ),
    path(
        "bulk/create/",
        views.BulkExistingLoanPaymentCreateView.as_view(),
        name="existing-loan-payment-bulk-create",
    ),
    path(
        "<str:reference>/",
        views.ExistingLoanPaymentDetailView.as_view(),
        name="existing-loan-payment-detail",
    ),
]
