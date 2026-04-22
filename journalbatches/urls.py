from django.urls import path

from journalbatches.views import (
    JournalBatchListCreateView,
    JournalBatchDetailView,
    BulkJournalBatchUploadView,
    BulkJournalBatchCreateView,
    JournalBatchTemplateDownloadView,
)

urlpatterns = [
    path("", JournalBatchListCreateView.as_view(), name="journalbatch-list-create"),
    path(
        "bulk/template/",
        JournalBatchTemplateDownloadView.as_view(),
        name="bulk-template",
    ),
    path("bulk/upload/", BulkJournalBatchUploadView.as_view(), name="bulk-upload"),
    path("bulk/create/", BulkJournalBatchCreateView.as_view(), name="bulk-create"),
    path(
        "<str:reference>/", JournalBatchDetailView.as_view(), name="journalbatch-detail"
    ),
]
