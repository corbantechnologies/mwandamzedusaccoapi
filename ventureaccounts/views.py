from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from ventureaccounts.models import VentureAccount
from ventureaccounts.serializers import VentureAccountSerializer


class VentureAccountListCreateView(generics.ListCreateAPIView):
    queryset = VentureAccount.objects.all().prefetch_related(
        "payments", "deposits", "venture_type_details"
    )
    serializer_class = VentureAccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def get_queryset(self):
        return self.queryset.filter(member=self.request.user)


class VentureAccountDetailView(generics.RetrieveAPIView):
    queryset = VentureAccount.objects.all().prefetch_related(
        "payments", "deposits", "venture_type_details"
    )
    serializer_class = VentureAccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]
    lookup_field = "identity"

    def get_queryset(self):
        return self.queryset.filter(member=self.request.user)
