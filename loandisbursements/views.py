from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from loandisbursements.models import LoanDisbursement
from loandisbursements.serializers import LoanDisbursementSerializer
from accounts.permissions import IsSystemAdminOrReadOnly
from loandisbursements.utils import send_disbursement_made_email


class LoanDisbursementListCreateView(generics.ListCreateAPIView):
    queryset = LoanDisbursement.objects.all()
    serializer_class = LoanDisbursementSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        disbursement = serializer.save(disbursed_by=self.request.user)
        # Update the loan application status to Disbursed
        loan_application = disbursement.loan_account.loan_application
        loan_application.status = "Disbursed"
        loan_application.save()
        # send email to the account owner if they have an email
        account_owner = disbursement.loan_account.member
        if account_owner.email:
            send_disbursement_made_email(account_owner, disbursement)


class LoanDisbursementDetailView(generics.RetrieveAPIView):
    queryset = LoanDisbursement.objects.all()
    serializer_class = LoanDisbursementSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"
