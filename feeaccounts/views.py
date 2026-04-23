from rest_framework import generics

from feeaccounts.models import FeeAccount
from feeaccounts.serializers import FeeAccountSerializer
from accounts.permissions import IsSystemAdminOrReadOnly


class FeeAccountListCreateView(generics.ListCreateAPIView):
    queryset = FeeAccount.objects.all()
    serializer_class = FeeAccountSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def get_queryset(self):
        if (
            self.request.user.is_sacco_admin
            or self.request.user.is_sacco_staff
            or self.request.user.is_treasurer
            or self.request.user.is_bookkeeper
            or self.request.user.is_superuser
        ):
            return self.queryset.all()
        return self.queryset.filter(member=self.request.user)


class FeeAccountDetailView(generics.RetrieveUpdateAPIView):
    queryset = FeeAccount.objects.all()
    serializer_class = FeeAccountSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"

    def get_queryset(self):
        if (
            self.request.user.is_sacco_admin
            or self.request.user.is_sacco_staff
            or self.request.user.is_treasurer
            or self.request.user.is_bookkeeper
            or self.request.user.is_superuser
        ):
            return self.queryset.all()
        return self.queryset.filter(member=self.request.user)
