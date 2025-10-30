from rest_framework import generics

from venturetypes.models import VentureType
from accounts.permissions import IsSystemAdminOrReadOnly
from venturetypes.serializers import VentureTypeSerializer


class VentureTypeListView(generics.ListCreateAPIView):
    queryset = VentureType.objects.all()
    serializer_class = VentureTypeSerializer
    permission_classes = [IsSystemAdminOrReadOnly]


class VentureTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = VentureType.objects.all()
    serializer_class = VentureTypeSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"
