from django.urls import path
from auditlogs.views import AuditLogListView

urlpatterns = [
    path('', AuditLogListView.as_view(), name='auditlog-list'),
]
