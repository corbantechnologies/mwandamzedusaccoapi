from rest_framework import generics, status
from rest_framework.response import Response
from loanapplications.models import LoanApplication
from loanapplications.serializers import LoanApplicationSerializer
from rest_framework.permissions import IsAuthenticated


class LoanApplicationListCreateView(generics.ListCreateAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)


class LoanApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"
