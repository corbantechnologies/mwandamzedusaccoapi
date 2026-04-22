from rest_framework import generics

from savings.models import SavingsAccount
from savings.serializers import SavingSerializer
from accounts.permissions import IsSystemAdminOrReadOnly


class SavingListCreateView(generics.ListCreateAPIView):
    queryset = SavingsAccount.objects.all().prefetch_related(
        "deposits",
    )
    serializer_class = SavingSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    # def perform_create(self, serializer):
    #     serializer.save(member=self.request.user)

    def get_queryset(self):
        if (
            self.request.user.is_sacco_admin
            or self.request.user.is_sacco_staff
            or self.request.user.is_treasurer
            or self.request.user.is_bookkeeper
            or self.request.user.is_superuser
        ):
            return self.queryset
        return self.queryset.filter(member=self.request.user)


class SavingDetailView(generics.RetrieveUpdateAPIView):
    queryset = SavingsAccount.objects.all().prefetch_related(
        "deposits",
    )
    serializer_class = SavingSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"

    def get_queryset(self):
        if (
            self.request.user.is_sacco_admin
            or self.request.user.is_sacco_staff
            or self.request.user.is_treasurer
            or self.request.user.is_bookkeeper
            or self.request.user.is_superuser
        ):
            return self.queryset
        return self.queryset.filter(member=self.request.user)
