from rest_framework import serializers
from auditlogs.models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_member_no = serializers.CharField(source='user.member_no', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = '__all__'
