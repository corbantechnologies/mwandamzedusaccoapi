from django.urls import path

from savingsdeposits.views import (
    SavingsDepositListCreateView,
    SavingsDepositView,
    BulkSavingsDepositView,
    BulkSavingsDepositUploadView,
    AdminSavingsDepositCreateView,
    SavingsDepositTemplateDownloadView,
)

app_name = "savingsdeposits"

urlpatterns = [
    path("", SavingsDepositListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", SavingsDepositView.as_view(), name="detail"),
    path("bulk/create/", BulkSavingsDepositView.as_view(), name="bulk-create"),
    path("bulk/upload/", BulkSavingsDepositUploadView.as_view(), name="bulk-upload"),
    path(
        "bulk/template/",
        SavingsDepositTemplateDownloadView.as_view(),
        name="bulk-template",
    ),
    path("admin/create/", AdminSavingsDepositCreateView.as_view(), name="admin-create"),
]
