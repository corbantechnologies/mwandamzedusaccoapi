from rest_framework import generics

from loanaccounts.serializers import LoanAccountSerializer
from loanaccounts.models import LoanAccount
from accounts.permissions import IsSystemAdminOrReadOnly


class LoanAccountListCreateView(generics.ListCreateAPIView):
    queryset = LoanAccount.objects.all().prefetch_related(
        "disbursements",
        "loan_payments",
    )
    serializer_class = LoanAccountSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]


class LoanAccountDetailView(generics.RetrieveUpdateAPIView):
    queryset = LoanAccount.objects.all().prefetch_related(
        "disbursements",
        "loan_payments",
    )
    serializer_class = LoanAccountSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"


class LoanAccountCreatedByAdminView(generics.ListCreateAPIView):
    queryset = LoanAccount.objects.all().prefetch_related(
        "disbursements",
        "loan_payments",
    )
    serializer_class = LoanAccountSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
