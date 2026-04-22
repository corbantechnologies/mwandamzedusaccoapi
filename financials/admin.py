from django.contrib import admin

# Register your models here.

from financials.models import PostingLog


@admin.register(PostingLog)
class PostingLogAdmin(admin.ModelAdmin):
    list_display = ("reference", "record", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("reference", "record")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
