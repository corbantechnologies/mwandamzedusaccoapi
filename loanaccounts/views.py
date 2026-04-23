from rest_framework import generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from loanaccounts.serializers import LoanAccountSerializer
from loanaccounts.models import LoanAccount
from accounts.permissions import IsSystemAdminOrReadOnly
from loanpayments.services import calculate_early_payoff_amounts


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


class LoanPayoffQuoteView(generics.RetrieveAPIView):
    """
    Returns the required (Principal, Interest, Fee) to close the loan today.
    """

    queryset = LoanAccount.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def retrieve(self, request, *args, **kwargs):
        loan_acc = self.get_object()
        p, i, f = calculate_early_payoff_amounts(loan_acc)
        return Response(
            {
                "principal_to_clear": p,
                "interest_to_recognize": i,
                "unpaid_fees": f,
                "total_payoff_amount": p + i + f,
            }
        )
