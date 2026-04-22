from django.contrib import admin

from mpesa.models import MpesaBody


@admin.register(MpesaBody)
class MpesaBodyAdmin(admin.ModelAdmin):
    list_display = ["reference", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["reference"]
    ordering = ["-created_at"]
