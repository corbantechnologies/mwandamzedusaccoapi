import logging
import requests
import base64
import threading
from datetime import datetime
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.conf import settings

from mpesa.utils import get_access_token
from mpesa.models import MpesaBody
from mpesa.serializers import MpesaBodySerializer
from savingsdeposits.models import SavingsDeposit
from savingsdeposits.utils import send_deposit_made_email
from savings.models import SavingsAccount

logger = logging.getLogger(__name__)


class MpesaPaymentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):


        try:
            deposit_reference = request.data.get("deposit_reference")
            phone_number = request.data.get("phone_number")

            if not deposit_reference:
                logger.error("No deposit reference provided")
                return Response(
                    {"error": "No deposit reference provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not phone_number:
                logger.error("No phone number provided")
                return Response(
                    {"error": "No phone number provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            deposit = SavingsDeposit.objects.get(reference=deposit_reference)

            if deposit.payment_status == "COMPLETED":
                logger.error("Deposit already completed")
                return Response(
                    {"error": "Deposit already completed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if deposit.transaction_status != "Pending":
                logger.error("Deposit is not pending")
                return Response(
                    {"error": "Deposit is not pending"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # validate M-Pesa Credentials
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
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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

            # Prepare STK Push Payload

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
            ).decode()

            payload = {
                "BusinessShortCode": settings.MPESA_SHORTCODE,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(deposit.amount),
                "PartyA": phone_number,
                "PartyB": settings.MPESA_SHORTCODE,
                "PhoneNumber": phone_number,
                "CallBackURL": settings.MPESA_CALLBACK_URL,
                "AccountReference": f"{deposit.savings_account.account_number}",
                "TransactionDesc": f"Mwanda Mzedu SACCO Deposit {deposit.savings_account.account_number}",
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
                    deposit.checkout_request_id = response_data.get("CheckoutRequestID")
                    deposit.callback_url = settings.MPESA_CALLBACK_URL
                    deposit.payment_method = "Mpesa STK Push"
                    deposit.mpesa_phone_number = phone_number
                    deposit.save()

                    return Response(
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
                        },
                        status=status.HTTP_200_OK,
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
                logger.error(f"M-Pesa STK Push request failed: {str(e)}")
                return Response(
                    {"error": "STK Push request failed"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except SavingsDeposit.DoesNotExist:
            logger.error("Deposit not found")
            return Response(
                {"error": "Deposit not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception as e:
            logger.error(f"M-Pesa STK Push request failed: {str(e)}")
            return Response(
                {"error": "STK Push request failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MpesaCallbackView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
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
        except SavingsDeposit.DoesNotExist:
            logger.error("Deposit not found")
            return Response(
                {"ResultCode": 0, "ResultDesc": "Deposit not found"},
                status=status.HTTP_200_OK,
            )

        # prevent duplicate processing
        if deposit.payment_status == "COMPLETED":
            logger.info("Deposit already processed")
            return Response(
                {"ResultCode": 0, "ResultDesc": "Deposit already processed"},
                status=status.HTTP_200_OK,
            )

        result_code = stk_callback.get("ResultCode")

        if result_code != 0:
            deposit.transaction_status = "Failed"
            deposit.payment_status = "FAILED"
            deposit.payment_status_description = stk_callback.get(
                "ResultDesc", "Payment failed"
            )
            deposit.save()

            logger.error("Deposit failed")
            return Response(
                {"ResultCode": 0, "ResultDesc": "Deposit failed"},
                status=status.HTTP_200_OK,
            )

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

        deposit.transaction_status = "Completed"
        deposit.payment_status = "COMPLETED"
        deposit.payment_status_description = "Payment completed"
        deposit.confirmation_code = confirmation_code
        deposit.payment_account = payment_account
        deposit.mpesa_receipt_number = confirmation_code
        deposit.mpesa_phone_number = payment_account
        deposit.payment_date = datetime.now()
        deposit.save()

        # Update savings account balance
        deposit.savings_account.balance += deposit.amount
        deposit.savings_account.save()
        deposit.save()

        logger.info("Deposit processed successfully")
        return Response(
            {"ResultCode": 0, "ResultDesc": "Deposit processed successfully"},
            status=status.HTTP_200_OK,
        )

    def get(self, request, *args, **kwargs):
        """Endpoint to view all saved callback bodies (for debugging)"""
        bodies = MpesaBody.objects.all().order_by("-id")
        serializer = MpesaBodySerializer(bodies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
