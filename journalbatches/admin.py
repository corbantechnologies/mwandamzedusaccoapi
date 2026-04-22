from django.contrib import admin

from journalbatches.models import JournalBatch


@admin.register(JournalBatch)
class JournalBatchAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "posted", "created_at", "updated_at")
    list_filter = ("posted", "created_at", "updated_at")
    search_fields = ("code", "description")
    ordering = ("-created_at",)
