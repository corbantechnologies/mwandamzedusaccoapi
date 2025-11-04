from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from guaranteerequests.models import GuaranteeRequest
from guaranteerequests.serializers import GuaranteeRequestSerializer


class GuaranteeRequestListCreateView(generics.ListCreateAPIView):
    """
    - Member makes a request
    """
    queryset = GuaranteeRequest.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = GuaranteeRequestSerializer
