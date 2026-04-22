from django.urls import path

from glaccounts.views import (
    GLAccountListCreateView,
    GLAccountDetailView,
    BulkGLAccountUploadView,
    GLAccountTemplateDownloadView,
    BulkGLAccountCreateView,
)

urlpatterns = [
    path("", GLAccountListCreateView.as_view(), name="glaccount-list-create"),
    path(
        "bulk/upload/", BulkGLAccountUploadView.as_view(), name="glaccount-bulk-upload"
    ),
    path(
        "bulk/template/",
        GLAccountTemplateDownloadView.as_view(),
        name="glaccount-bulk-template",
    ),
    path(
        "bulk/create/", BulkGLAccountCreateView.as_view(), name="glaccount-bulk-create"
    ),
    path("<str:reference>/", GLAccountDetailView.as_view(), name="glaccount-detail"),
]
