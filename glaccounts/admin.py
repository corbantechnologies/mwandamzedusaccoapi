from django.contrib import admin

from glaccounts.models import GLAccount


@admin.register(GLAccount)
class GLAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "balance")
    list_filter = ("category",)
    search_fields = ("code", "name")
    ordering = ("code",)
