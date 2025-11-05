from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from guaranteerequests.models import GuaranteeRequest
from guaranteerequests.serializers import GuaranteeRequestSerializer


class GuaranteeRequestListCreateView(generics.ListCreateAPIView):
    """
    - Member makes a request
    """

    queryset = GuaranteeRequest.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = GuaranteeRequestSerializer

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def get_queryset(self):
        # both the member and guarantor can see the request
        # guarantors should see requests made to them
        user = self.request.user
        return (
            super()
            .get_queryset()
            .filter(Q(member=user) | Q(guarantor__member=user))
            .select_related("member", "guarantor__member", "loan_application")
        )


class GuaranteeRequestRetrieveView(generics.RetrieveAPIView):
    serializer_class = GuaranteeRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def get_queryset(self):
        return GuaranteeRequest.objects.filter(
            Q(member=self.request.user) | Q(guarantor__member=self.request.user)
        )


class GuaranteeRequestUpdateStatusView(generics.UpdateAPIView):
    serializer_class = GuaranteeRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def get_queryset(self):
        return GuaranteeRequest.objects.filter(guarantor__member=self.request.user)

    def get_serializer(self, *args, **kwargs):
        kwargs["partial"] = True
        serializer = super().get_serializer(*args, **kwargs)
        # Only allow 'status'
        for field in serializer.fields:
            if field != "status":
                serializer.fields[field].read_only = True
        return serializer
