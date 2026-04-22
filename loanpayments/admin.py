from django.contrib import admin

from loanpayments.models import LoanPayment


@admin.register(LoanPayment)
class LoanPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_code",
        "loan_account",
        "paid_by",
        "amount",
        "payment_method",
        "repayment_type",
        "transaction_status",
        "payment_date",
    )
    list_filter = (
        "payment_method",
        "repayment_type",
        "transaction_status",
        "payment_date",
    )
    search_fields = (
        "payment_code",
        "loan_account__account_number",
        "paid_by__member_no",
    )
    ordering = ("-payment_date",)
