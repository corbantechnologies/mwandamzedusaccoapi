from rest_framework import generics

from savingtypes.models import SavingType
from savingtypes.serializers import SavingTypeSerializer
from accounts.permissions import IsSystemAdminOrReadOnly


class SavingTypeListCreateView(generics.ListCreateAPIView):
    queryset = SavingType.objects.all()
    serializer_class = SavingTypeSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)


class SavingTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SavingType.objects.all()
    serializer_class = SavingTypeSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)
    lookup_field = "reference"