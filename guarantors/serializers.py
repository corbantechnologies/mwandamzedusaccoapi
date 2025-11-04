from rest_framework import serializers

from guarantors.models import GuarantorProfile


class GuarantorProfileSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no")

    class Meta:
        model = GuarantorProfile
        fields = (
            "member",
            "is_eligible",
            "eligibility_checked_at",
            "max_active_guarantees",
            "max_guarantee_amount",
            "reference",
            "created_at",
            "updated_at",
        )
