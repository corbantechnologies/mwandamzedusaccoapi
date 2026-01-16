from django.urls import path

from savingsdeposits.views import (
    SavingsDepositListCreateView,
    SavingsDepositView,
    BulkSavingsDepositView,
    BulkSavingsDepositUploadView,
    AdminSavingsDepositCreateView,
)

app_name = "savingsdeposits"

urlpatterns = [
    path("", SavingsDepositListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", SavingsDepositView.as_view(), name="detail"),
    path("bulk/", BulkSavingsDepositView.as_view(), name="bulk-create"),
    path("bulk/upload/", BulkSavingsDepositUploadView.as_view(), name="bulk-upload"),
    path(
        "admin/create/", AdminSavingsDepositCreateView.as_view(), name="admin-create"
    ),
]
