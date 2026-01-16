from django.db import models


class MpesaPaymentModel(models.Model):
    MPESA_PAYMENT_STATUS_CHOICES = (
        ("PENDING", "PENDING"),
        ("COMPLETED", "COMPLETED"),
        ("CANCELLED", "CANCELLED"),
        ("FAILED", "FAILED"),
        ("REVERSED", "REVERSED"),
    )
    checkout_request_id = models.CharField(max_length=2550, blank=True, null=True)
    callback_url = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(
        max_length=20, choices=MPESA_PAYMENT_STATUS_CHOICES, default="PENDING"
    )
    payment_status_description = models.CharField(max_length=100, blank=True, null=True)
    confirmation_code = models.CharField(max_length=100, blank=True, null=True)
    payment_account = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateTimeField(blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=2550, blank=True, null=True)
    mpesa_phone_number = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        abstract = True
