from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

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
    permission_classes = [IsAuthenticated]
    lookup_field = "member__member_no"
    lookup_url_kwarg = "member"
