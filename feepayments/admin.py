from django.contrib import admin
from feepayments.models import FeePayment


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "fee_account",
        "paid_by",
        "amount",
        "payment_method",
        "transaction_status",
        "transaction_date",
        "created_at",
    )
    list_filter = (
        "payment_method",
        "transaction_status",
        "transaction_date",
        "created_at",
    )
    search_fields = ("code", "fee_account__account_number")
    ordering = ("-created_at",)

