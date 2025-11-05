from rest_framework import generics

from guarantors.serializers import GuarantorProfileSerializer
from guarantors.models import GuarantorProfile
from accounts.permissions import IsSystemAdminOrReadOnly


class GuarantorProfileListCreateView(generics.ListCreateAPIView):
    queryset = GuarantorProfile.objects.all()
    serializer_class = GuarantorProfileSerializer
    permission_classes = [IsSystemAdminOrReadOnly]


class GuarantorProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = GuarantorProfile.objects.all()
    serializer_class = GuarantorProfileSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"
