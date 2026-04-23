from django.contrib import admin

from existingloanspayments.models import ExistingLoanPayment


@admin.register(ExistingLoanPayment)
class ExistingLoanPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "existing_loan",
        "paid_by",
        "amount",
        "transaction_status",
        "payment_date",
    )
    list_filter = (
        "transaction_status",
        "payment_date",
    )
    search_fields = (
        "reference",
        "existing_loan__reference",
        "paid_by__username",
    )
    ordering = ("-payment_date",)
