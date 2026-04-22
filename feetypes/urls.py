from django.urls import path

from feetypes import views

app_name = "feetypes"

urlpatterns = [
    path("", views.FeeTypeListCreateView.as_view(), name="fee-type-list"),
    path(
        "bulk/template/",
        views.FeeTypeTemplateDownloadView.as_view(),
        name="fee-type-bulk-template",
    ),
    path(
        "bulk/upload/",
        views.BulkFeeTypeUploadView.as_view(),
        name="fee-type-bulk-upload",
    ),
    path(
        "bulk/create/",
        views.BulkFeeTypeCreateView.as_view(),
        name="fee-type-bulk-create",
    ),
    path("<str:reference>/", views.FeeTypeDetailView.as_view(), name="fee-type-detail"),
]
