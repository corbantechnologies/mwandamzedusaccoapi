from django.db import models
from accounts.abstracts import UniversalIdModel, TimeStampedModel, ReferenceModel
from django.conf import settings

class AuditLog(UniversalIdModel, TimeStampedModel, ReferenceModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    action = models.CharField(max_length=255)
    module = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.user} - {self.created_at}"
