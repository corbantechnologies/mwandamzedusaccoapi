from rest_framework import generics

from savings.models import SavingsAccount
from savings.serializers import SavingSerializer
from accounts.permissions import IsSystemAdminOrReadOnly


class SavingListCreateView(generics.ListCreateAPIView):
    queryset = SavingsAccount.objects.all()
    serializer_class = SavingSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def get_queryset(self):
        return self.queryset.filter(member=self.request.user)


class SavingDetailView(generics.RetrieveUpdateAPIView):
    queryset = SavingsAccount.objects.all()
    serializer_class = SavingSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "identity"

    def get_queryset(self):
        return self.queryset.filter(member=self.request.user)
