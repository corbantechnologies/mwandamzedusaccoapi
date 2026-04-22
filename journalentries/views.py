from rest_framework import generics

from journalentries.models import JournalEntry
from journalentries.serializers import JournalEntrySerializer
from accounts.permissions import IsSystemAdminOrReadOnly


class JournalEntryListCreateView(generics.ListCreateAPIView):
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class JournalEntryDetailView(generics.RetrieveUpdateAPIView):
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"

    def get_object(self):
        obj = super().get_object()
        if self.request.method in ["PUT", "PATCH"] and obj.batch.posted:
            raise serializers.ValidationError(
                "You cannot update a posted journal entry."
            )
        return obj

    def perform_update(self, serializer):
        # only sacco-admins can update journals
        if self.request.user.is_sacco_admin:
            serializer.save(updated_by=self.request.user)
        else:
            raise serializers.ValidationError("You cannot update a journal entry.")
