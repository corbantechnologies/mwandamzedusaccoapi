from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from loanpayments.models import LoanPayment
from loanpayments.serializers import LoanPaymentSerializer
from loanpayments.utils import send_loan_payment_made_email


class LoanPaymentCreateView(generics.ListCreateAPIView):
    queryset = LoanPayment.objects.all()
    serializer_class = LoanPaymentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Save first to ensure instance exists and signal runs
        instance = serializer.save(paid_by=self.request.user)

        # send an email to the user after successful creation and status is completed
        if instance.transaction_status == "Completed":
            send_loan_payment_made_email(self.request.user, instance)


class LoanPaymentDetailView(generics.RetrieveAPIView):
    queryset = LoanPayment.objects.all()
    serializer_class = LoanPaymentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"
