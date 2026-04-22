from django.contrib import admin

from paymentaccounts.models import PaymentAccount


@admin.register(PaymentAccount)
class PaymentAccountAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "reference", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["name", "reference"]
    ordering = ["-created_at"]
    readonly_fields = ["reference", "created_at", "updated_at"]
