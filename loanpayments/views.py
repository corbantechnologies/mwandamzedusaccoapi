from rest_framework import generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from loanpayments.models import LoanPayment
from loanpayments.serializers import LoanPaymentSerializer
from loanpayments.utils import (
    send_loan_payment_made_email,
    send_loan_payment_pending_update_email,
)
from loanpayments.services import process_loan_repayment_accounting


class LoanPaymentCreateView(generics.ListCreateAPIView):
    queryset = LoanPayment.objects.all()
    serializer_class = LoanPaymentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Use a transaction to ensure both DB save and Accounting succeed together
        with transaction.atomic():
            # 1. Save the payment record
            instance = serializer.save(paid_by=self.request.user)

            # 2. Trigger accounting only if status is Completed
            # (Admin payments usually default to Completed,
            # while M-Pesa starts as Pending and is handled in the callback)
            if instance.transaction_status == "Completed":
                process_loan_repayment_accounting(instance)

        # 3. Send email after the transaction is successfully committed
        if instance.transaction_status == "Completed":
            send_loan_payment_made_email(self.request.user, instance)


class LoanPaymentDetailView(generics.RetrieveAPIView):
    queryset = LoanPayment.objects.all()
    serializer_class = LoanPaymentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"


"""
M-Pesa Integration
"""


class LoanMpesaPaymentListCreateView(generics.ListCreateAPIView):
    """
    This view is used to create a new loan payment via M-Pesa.
    The Payment is logged and the admin will officiate it later.
    An email is sent to the user upon successful Mpesa payment notifying the user that the payment has been received and is pending approval.
    And that their loan account will be updated by end of business day.
    """

    queryset = LoanPayment.objects.all()
    serializer_class = LoanPaymentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(paid_by=self.request.user)

    def get_queryset(self):
        if (
            self.request.user.is_sacco_admin
            or self.request.user.is_sacco_staff
            or self.request.user.is_treasurer
            or self.request.user.is_bookkeeper
            or self.request.user.is_superuser
        ):
            return self.queryset
        return self.queryset.filter(paid_by=self.request.user)
