from django.contrib import admin

from loandisbursements.models import LoanDisbursement


class LoanDisbursementAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_code",
        "loan_account",
        "disbursed_by",
        "amount",
        "currency",
        "transaction_status",
        "disbursement_type",
    )
    search_fields = ("transaction_code", "loan_account__account_number")
    list_filter = ("transaction_status", "disbursement_type")
    ordering = ("-created_at",)


admin.site.register(LoanDisbursement, LoanDisbursementAdmin)
