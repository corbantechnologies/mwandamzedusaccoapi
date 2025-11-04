from rest_framework import serializers
from django.db import models

from guarantors.models import GuarantorProfile
from guaranteerequests.models import GuaranteeRequest


class GuarantorProfileSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no")
    active_guarantees_count = serializers.SerializerMethodField()
    committed_amount = serializers.SerializerMethodField()
    max_guarantee_amount = serializers.SerializerMethodField()
    has_reached_limit = serializers.SerializerMethodField()

    class Meta:
        model = GuarantorProfile
        fields = (
            "member",
            "is_eligible",
            "eligibility_checked_at",
            "max_active_guarantees",
            "max_guarantee_amount",
            "active_guarantees_count",
            "committed_amount",
            "has_reached_limit",
            "reference",
            "created_at",
            "updated_at",
        )

    def get_active_guarantees_count(self, obj):
        return GuaranteeRequest.objects.filter(guarantor=obj, status="Accepted").count()

    def get_committed_amount(self, obj):
        total = GuaranteeRequest.objects.filter(
            guarantor=obj, status="Accepted"
        ).aggregate(total=models.Sum("guaranteed_amount"))["total"]
        return float(total or 0)

    def get_max_guarantee_amount(self, obj):
        return float(obj.max_guarantee_amount)

    def get_has_reached_limit(self, obj):
        """
        Should be updated when the max_active_guarantees is changed
        """
        return self.get_active_guarantees_count(obj) >= obj.max_active_guarantees
