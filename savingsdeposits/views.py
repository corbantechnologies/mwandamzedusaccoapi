import requests
import csv
import io
import cloudinary.uploader
import logging
import threading
from decimal import Decimal
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.conf import settings
from rest_framework.views import APIView

from accounts.permissions import IsSystemAdminOrReadOnly
from savingsdeposits.models import SavingsDeposit
from savingsdeposits.serializers import (
    SavingsDepositSerializer,
    BulkSavingsDepositSerializer,
)
from savingsdeposits.utils import send_deposit_made_email
from datetime import date
from transactions.models import BulkTransactionLog
from django.db import transaction
from savingtypes.models import SavingType
from mpesa.models import MpesaBody
from savings.models import SavingsAccount
from mpesa.utils import get_access_token


logger = logging.getLogger(__name__)


class SavingsDepositListCreateView(generics.ListCreateAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        deposit = serializer.save(deposited_by=self.request.user)
        # Send email to the account owner if they have an email address
        account_owner = deposit.savings_account.member
        if account_owner.email:
            send_deposit_made_email(account_owner, deposit)


class SavingsDepositView(generics.RetrieveAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"


"""
Bulk Transactions:
- With JSON payload
- With file upload (CSV)
"""


class BulkSavingsDepositView(generics.CreateAPIView):
    serializer_class = BulkSavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        deposits_data = serializer.validated_data.get("deposits", [])
        admin = self.request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"SAVINGS-BULK-{date_str}"

        # Initialize log
        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Savings Deposits",
            reference_prefix=prefix,
            success_count=0,
            error_count=0,
        )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, deposit_data in enumerate(deposits_data, 1):
                try:
                    # Add deposited_by and reference
                    deposit_data["deposited_by"] = admin
                    deposit_data["reference"] = f"{prefix}-{index:04d}"
                    deposit_data["transaction_status"] = deposit_data.get(
                        "transaction_status", "Completed"
                    )
                    deposit_data["is_active"] = deposit_data.get("is_active", True)

                    # Create deposit
                    deposit_serializer = SavingsDepositSerializer(data=deposit_data)
                    if deposit_serializer.is_valid():
                        deposit = deposit_serializer.save()
                        success_count += 1
                        # Send email if account owner has email
                        account_owner = deposit.savings_account.member
                        if account_owner.email:
                            send_deposit_made_email(account_owner, deposit)
                    else:
                        error_count += 1
                        errors.append(
                            {"index": index, "errors": deposit_serializer.errors}
                        )
                except Exception as e:
                    error_count += 1
                    errors.append({"index": index, "error": str(e)})

            # Update log
            log.success_count = success_count
            log.error_count = error_count
            log.save()

        # Return response with summary
        response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
        }
        return Response(
            response_data,
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )


class BulkSavingsDepositUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk savings deposits."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = SavingsDepositSerializer  # Added for browsable API

    def post(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Read CSV
        try:
            csv_content = file.read().decode("utf-8")
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
        except Exception as e:
            logger.error(f"Failed to read CSV: {str(e)}")
            return Response(
                {"error": f"Invalid CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get savings types for validation
        try:
            savings_types = SavingType.objects.all().values_list("name", flat=True)
        except Exception as e:
            logger.error(f"Failed to fetch savings types: {str(e)}")
            return Response(
                {"error": "Failed to fetch savings types"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"SAVINGS-BULK-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Savings Deposits",
                reference_prefix=prefix,
                success_count=0,
                error_count=0,
                file_name=file.name,
            )
        except Exception as e:
            logger.error(f"Failed to create BulkTransactionLog: {str(e)}")
            return Response(
                {"error": "Failed to initialize transaction log"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Upload to Cloudinary
        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_savings/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result["secure_url"]
            log.save()
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")
            return Response(
                {"error": "Failed to upload file to storage"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, row in enumerate(reader, 1):
                try:
                    # Process each savings type
                    deposits_data = []
                    for stype in savings_types:
                        amount_key = f"{stype} Amount"
                        account_key = f"{stype} Account"
                        if amount_key in row and row[amount_key] and row[account_key]:
                            try:
                                amount = float(row[amount_key])
                                if amount < Decimal("0.01"):
                                    raise ValueError("Amount must be greater than 0")
                                deposit_data = {
                                    "savings_account": row[account_key],
                                    "amount": amount,
                                    "payment_method": row.get("Payment Method", "Cash"),
                                    "deposit_type": "Individual Deposit",
                                    "currency": "KES",
                                    "transaction_status": "Completed",
                                    "is_active": True,
                                }
                                deposits_data.append(deposit_data)
                            except ValueError as e:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "account": row.get(account_key),
                                        "error": str(e),
                                    }
                                )
                                continue

                    # Validate and save deposits
                    for deposit_data in deposits_data:
                        deposit_serializer = SavingsDepositSerializer(data=deposit_data)
                        if deposit_serializer.is_valid():
                            deposit = deposit_serializer.save(deposited_by=admin)
                            success_count += 1
                            account_owner = deposit.savings_account.member

                        else:
                            error_count += 1
                            errors.append(
                                {
                                    "row": index,
                                    "account": deposit_data["savings_account"],
                                    "error": str(deposit_serializer.errors),
                                }
                            )

                except Exception as e:
                    error_count += 1
                    errors.append({"row": index, "error": str(e)})

            # Update log
            try:
                log.success_count = success_count
                log.error_count = error_count
                log.save()
            except Exception as e:
                logger.error(f"Failed to update BulkTransactionLog: {str(e)}")
                return Response(
                    {"error": "Failed to update transaction log"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Return response
        response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
            "cloudinary_url": log.cloudinary_url,
        }
        try:
            return Response(
                response_data,
                status=(
                    status.HTTP_201_CREATED
                    if success_count > 0
                    else status.HTTP_400_BAD_REQUEST
                ),
            )
        except Exception as e:
            logger.error(f"Failed to return response: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


"""
M-Pesa Integration
"""


class MpesaSavingsDepositView(generics.CreateAPIView):
    permission_classes = [
        IsAuthenticated,
    ]
    serializer_class = SavingsDepositSerializer

    def post(self, request, *args, **kwargs):
        try:
            savings_account = request.data.get("savings_account")
            phone_number = request.data.get("phone_number")
            amount = request.data.get("amount")
            deposited_by = request.user

            if not savings_account:
                logger.error("Savings account not provided")
                return Response(
                    {"error": "Savings account not provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not phone_number:
                logger.error("Phone number not provided")
                return Response(
                    {"error": "Phone number not provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not amount:
                logger.error("Amount not provided")
                return Response(
                    {"error": "Amount not provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            savings_account = SavingsAccount.objects.filter(
                account_number=savings_account
            ).first()

            if not savings_account:
                logger.error("Savings account not found")
                return Response(
                    {"error": "Savings account not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # validate mpesa credentials
            if not all(
                [
                    settings.MPESA_CONSUMER_KEY,
                    settings.MPESA_CONSUMER_SECRET,
                    settings.MPESA_SHORTCODE,
                    settings.MPESA_PASSKEY,
                ]
            ):
                logger.error("M-Pesa credentials not configured")
                return Response(
                    {"error": "M-Pesa credentials not configured"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get access token
            try:
                access_token = get_access_token(
                    access_token_url=f"{settings.MPESA_API_URL}/oauth/v1/generate?grant_type=client_credentials",
                    consumer_key=settings.MPESA_CONSUMER_KEY,
                    consumer_secret=settings.MPESA_CONSUMER_SECRET,
                )
            except ValueError as e:
                logger.error(f"M-Pesa authentication failed: {str(e)}")
                return Response(
                    {"error": f"Authentication failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Prepare STK Push
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
            ).decode()

            payload = {
                "BusinessShortCode": settings.MPESA_SHORTCODE,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": settings.MPESA_SHORTCODE,
                "PhoneNumber": phone_number,
                "CallBackURL": settings.MPESA_CALLBACK_URL,
                "AccountReference": savings_account.account_number,
                "TransactionDesc": f"Deposit to {savings_account.account_number}",
            }

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            try:
                response = requests.post(
                    f"{settings.MPESA_API_URL}/mpesa/stkpush/v1/processrequest",
                    json=payload,
                    headers=headers,
                )
                response_data = response.json()
                logger.info(f"M-Pesa STK Push response: {response_data}")

                if response_data.get("ResponseCode") == "0":
                    checkout_request_id = response_data.get("CheckoutRequestID")
                    callback_url = response_data.get("CallbackURL")
                    payment_method = "M-Pesa STK Push"
                    mpesa_phone_number = phone_number

                    serializer = SavingsDepositSerializer(
                        data={
                            "savings_account": savings_account.account_number,
                            "phone_number": phone_number,
                            "amount": amount,
                            "checkout_request_id": checkout_request_id,
                            "callback_url": callback_url,
                            "payment_method": payment_method,
                            "mpesa_phone_number": mpesa_phone_number,
                        }
                    )

                    if serializer.is_valid(raise_exception=True):
                        serializer.save(deposited_by=deposited_by)

                    response_body = serializer.data
                    response_body.update(
                        {
                            "merchant_request_id": response_data.get(
                                "MerchantRequestID"
                            ),
                            "checkout_request_id": response_data.get(
                                "CheckoutRequestID"
                            ),
                            "response_description": response_data.get(
                                "ResponseDescription"
                            ),
                            "customer_message": response_data.get("CustomerMessage"),
                        }
                    )

                    return Response(
                        response_body,
                        status=status.HTTP_201_CREATED,
                    )
                else:
                    logger.error(f"M-Pesa STK Push failed: {response_data}")
                    return Response(
                        {
                            "error": response_data.get(
                                "errorMessage", "STK Push request failed"
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except requests.RequestException as e:
                logger.error(f"M-Pesa STK Push request exception: {str(e)}")
                return Response(
                    {"error": f"STK Push request failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error(f"M-Pesa STK Push failed: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MpesaSavingsDepositCallbackView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        body = request.data

        if not body:
            logger.error("Invalid or empty callback data")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Save raw callback for debugging
        MpesaBody.objects.create(body=body)

        stk_callback = body.get("Body", {}).get("stkCallback", {})
        checkout_request_id = stk_callback.get("CheckoutRequestID")

        if not checkout_request_id:
            logger.error("Missing CheckoutRequestID in callback")
            return Response(
                {"ResultCode": 1, "ResultDesc": "Invalid callback data"},
                status=status.HTTP_200_OK,
            )

        try:
            deposit = SavingsDeposit.objects.get(
                checkout_request_id=checkout_request_id
            )
        except:
            logger.error(
                "Deposit not found for CheckoutRequestID: %s", checkout_request_id
            )
            return Response(
                {"ResultCode": 1, "ResultDesc": "Deposit not found"},
                status=status.HTTP_200_OK,
            )

        # prevent duplicate callbacks
        if deposit.payment_status == "COMPLETED":
            return Response(
                {"ResultCode": 0, "ResultDesc": "Deposit already processed"},
                status=status.HTTP_200_OK,
            )

        result_code = stk_callback.get("ResultCode")

        if result_code != 0:
            deposit.payment_status = "FAILED"
            deposit.transaction_status = "Failed"
            deposit.payment_status_description = stk_callback.get("ResultDesc")
            deposit.save()
            return Response(
                {"ResultCode": 0, "ResultDesc": "Payment failed acknowledged"},
                status=status.HTTP_200_OK,
            )

        # SUCCESS PATH
        metadata_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])

        confirmation_code = next(
            (
                item.get("Value")
                for item in metadata_items
                if item.get("Name") == "MpesaReceiptNumber"
            ),
            None,
        )
        payment_account = next(
            (
                item.get("Value")
                for item in metadata_items
                if item.get("Name") == "PhoneNumber"
            ),
            None,
        )

        deposit.payment_status = "COMPLETED"
        deposit.transaction_status = "Completed"
        deposit.payment_status_description = stk_callback.get("ResultDesc")
        deposit.confirmation_code = confirmation_code
        deposit.payment_account = payment_account
        deposit.save()

        # send notification to user

        if deposit.deposited_by.email:
            threading.Thread(
                target=send_savings_deposit_confirmation_email,
                args=(deposit.deposited_by, deposit),
            ).start()

        return Response(
            {"ResultCode": 0, "ResultDesc": "Payment successful"},
            status=status.HTTP_200_OK,
        )

    def get(self, request, *args, **kwargs):
        """Endpoint to view all saved callback bodies (for debugging)"""
        bodies = MpesaBody.objects.all().order_by("-id")
        serializer = MpesaBodySerializer(bodies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
