from django.contrib import admin
from .models import LoanPenalty


@admin.register(LoanPenalty)
class LoanPenaltyAdmin(admin.ModelAdmin):
    list_display = (
        "penalty_code",
        "loan_account",
        "installment_code",
        "amount",
        "status",
        "charged_by",
        "created_at",
    )
    list_filter = ("status", "charged_by", "created_at")
    search_fields = (
        "penalty_code",
        "loan_account__account_number",
        "installment_code",
        "charged_by__username",
    )
    readonly_fields = ("penalty_code", "created_at", "updated_at")
    ordering = ("-created_at",)
