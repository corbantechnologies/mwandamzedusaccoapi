from django.contrib import admin

from auditlogs.models import AuditLog

# Register your models here.
admin.site.register(AuditLog)