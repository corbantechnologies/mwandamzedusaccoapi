from django.urls import path

from journalentries.views import JournalEntryListCreateView, JournalEntryDetailView

urlpatterns = [
    path("", JournalEntryListCreateView.as_view(), name="journal-entry-list-create"),
    path(
        "<str:reference>/",
        JournalEntryDetailView.as_view(),
        name="journal-entry-detail",
    ),
]
