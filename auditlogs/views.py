from django.shortcuts import render

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from auditlogs.models import AuditLog
from auditlogs.serializers import AuditLogSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

class AuditLogListView(generics.ListAPIView):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['user', 'action', 'module']
    search_fields = ['description', 'action', 'module']
