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
            or self.request.user.is_superuser
        ):
            return self.queryset
        return self.queryset.filter(paid_by=self.request.user)


class LoanRepaymentTemplateDownloadView(generics.GenericAPIView):
    """
    Endpoint to download a CSV template for bulk Loan Repayment upload.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        import csv
        from django.http import HttpResponse
        from loanaccounts.models import LoanAccount
        
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="loan_payments_bulk_template.csv"'

        writer = csv.writer(response)
        writer.writerow(["Loan Account Number", "Repayment Type", "Amount", "Payment Method", "Transaction Date"])
        
        # Populate with active/outstanding loans
        active_loans = LoanAccount.objects.filter(outstanding_balance__gt=0).select_related("member")
        for loan in active_loans:
            writer.writerow([
                loan.account_number,
                "Regular Repayment",
                "",
                "",
                ""
            ])
        return response


class BulkLoanRepaymentUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk Loan Repayment creation."""
    permission_classes = [IsAuthenticated]
    from loanpayments.serializers import BulkUploadFileSerializer
    serializer_class = BulkUploadFileSerializer

    def post(self, request, *args, **kwargs):
        import csv
        import io
        import logging
        from datetime import date, datetime
        import cloudinary.uploader
        from transactions.models import BulkTransactionLog
        from loanpayments.serializers import LoanPaymentSerializer
        
        logger = logging.getLogger(__name__)
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            csv_content = file.read().decode("utf-8")
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
        except Exception as e:
            return Response({"error": f"Invalid CSV file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        admin = request.user
        today = date.today()
        prefix = f"LN-PYMT-BULK-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Loan Payments Upload",
            reference_prefix=prefix,
            file_name=file.name,
        )

        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_loanpayments/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result["secure_url"]
            log.save()
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, row in enumerate(reader, 1):
                try:
                    loan_acc = row.get("Loan Account Number") or row.get("loan_account", "").strip()
                    amount = row.get("Amount", "0.00").strip()
                    pmethod = row.get("Payment Method", "").strip()
                    rtype = row.get("Repayment Type", "Regular Repayment").strip()
                    raw_date = row.get("Transaction Date") or row.get("transaction_date")

                    if not loan_acc or not amount:
                        continue

                    row_data = {
                        "loan_account": loan_acc,
                        "amount": amount,
                        "payment_method": pmethod,
                        "repayment_type": rtype,
                        "transaction_status": "Completed",
                    }
                    if raw_date:
                        try:
                            datetime.strptime(raw_date.strip(), "%Y-%m-%d")
                            row_data["transaction_date"] = raw_date.strip()
                        except ValueError:
                            pass

                    temp_serializer = LoanPaymentSerializer(data=row_data)
                    if temp_serializer.is_valid():
                        instance = temp_serializer.save(paid_by=admin)
                        process_loan_repayment_accounting(instance)
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "loan": loan_acc,
                                "error": str(temp_serializer.errors),
                            }
                        )
                except Exception as e:
                    error_count += 1
                    errors.append({"row": index, "error": str(e)})

            log.success_count = success_count
            log.error_count = error_count
            log.save()

        return Response(
            {
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors,
                "log_reference": log.reference_prefix,
                "cloudinary_url": log.cloudinary_url,
            },
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )


class BulkLoanRepaymentCreateView(generics.CreateAPIView):
    """Bulk creation of Loan Payments via JSON payload."""
    permission_classes = [IsAuthenticated]
    from loanpayments.serializers import BulkLoanPaymentSerializer
    serializer_class = BulkLoanPaymentSerializer

    def perform_create(self, serializer):
        from datetime import date
        from transactions.models import BulkTransactionLog
        
        payments_data = serializer.validated_data.get("payments", [])
        admin = self.request.user
        today = date.today()
        prefix = f"LN-PYMT-BULK-JSON-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Loan Payments Bulk JSON",
            reference_prefix=prefix,
        )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, payment_data in enumerate(payments_data, 1):
                try:
                    payment_data["transaction_status"] = "Completed"
                    instance = LoanPayment.objects.create(
                        **payment_data, paid_by=admin
                    )
                    process_loan_repayment_accounting(instance)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append({"index": index, "error": str(e)})

            log.success_count = success_count
            log.error_count = error_count
            log.save()

        self.response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
        }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            self.response_data,
            status=(
                status.HTTP_201_CREATED
                if self.response_data["success_count"] > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )
