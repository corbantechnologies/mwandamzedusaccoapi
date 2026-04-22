from django.urls import path

from existingloans import views

app_name = "existingloans"

urlpatterns = [
    path("", views.ExistingLoanListCreateView.as_view(), name="existing-loan-list"),
    path(
        "bulk/template/",
        views.ExistingLoanTemplateDownloadView.as_view(),
        name="existing-loan-bulk-template",
    ),
    path(
        "bulk/upload/",
        views.BulkExistingLoanUploadView.as_view(),
        name="existing-loan-bulk-upload",
    ),
    path(
        "bulk/create/",
        views.BulkExistingLoanCreateView.as_view(),
        name="existing-loan-bulk-create",
    ),
    path(
        "<str:reference>/",
        views.ExistingLoanDetailView.as_view(),
        name="existing-loan-detail",
    ),
]
