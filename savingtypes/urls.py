from django.urls import path

from savingtypes.views import (
    SavingTypeListCreateView,
    SavingTypeDetailView,
    SavingTypeTemplateDownloadView,
    BulkSavingTypeUploadView,
    BulkSavingTypeCreateView,
)

app_name = "savingtypes"

urlpatterns = [
    path("", SavingTypeListCreateView.as_view(), name="savingtypes"),
    path(
        "bulk/template/",
        SavingTypeTemplateDownloadView.as_view(),
        name="savingtypes-bulk-template",
    ),
    path(
        "bulk/upload/",
        BulkSavingTypeUploadView.as_view(),
        name="savingtypes-bulk-upload",
    ),
    path(
        "bulk/create/",
        BulkSavingTypeCreateView.as_view(),
        name="savingtypes-bulk-create",
    ),
    path("<str:reference>/", SavingTypeDetailView.as_view(), name="savingtype-detail"),
]
