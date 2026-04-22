from django.contrib import admin

from journalentries.models import JournalEntry


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("code", "batch", "account", "debit", "credit")
    list_filter = ("batch", "account")
    search_fields = ("code", "batch__code", "account__code")
