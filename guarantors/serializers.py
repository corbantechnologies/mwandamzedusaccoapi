from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import models
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from mwandamzeduapi.settings import MEMBER_PERIOD
from guarantors.models import GuarantorProfile
from savings.models import SavingsAccount

User = get_user_model()


class GuarantorProfileSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    member_no = serializers.CharField(write_only=True)

    active_guarantees_count = serializers.SerializerMethodField()
    committed_amount = serializers.SerializerMethodField()
    available_amount = serializers.SerializerMethodField()
    has_reached_limit = serializers.SerializerMethodField()

    class Meta:
        model = GuarantorProfile
        fields = (
            "member_no",
            "member",
            "is_eligible",
            "eligibility_checked_at",
            "max_active_guarantees",
            "active_guarantees_count",
            "committed_amount",
            "available_amount",
            "has_reached_limit",
            "reference",
            "created_at",
            "updated_at",
        )

    def validate(self, data):
        if data.get("is_eligible"):
            member_no = data.get("member_no")
            if not member_no:
                raise serializers.ValidationError(
                    {"member_no": "This field is required."}
                )

            try:
                member = User.objects.get(member_no=member_no)
            except User.DoesNotExist:
                raise serializers.ValidationError({"member_no": "Member not found."})

            months = int(MEMBER_PERIOD)
            required_date = timezone.now() - relativedelta(months=months)
            if member.created_at and member.created_at > required_date:
                raise serializers.ValidationError(
                    {
                        "is_eligible": f"Member must be in SACCO for {months}+ months to be eligible."
                    }
                )

        member_no = data.get("member_no")
        if member_no:
            try:
                member = User.objects.get(member_no=member_no)
                if GuarantorProfile.objects.filter(member=member).exists():
                    raise serializers.ValidationError(
                        {"member_no": "Member already has a Guarantor Profile."}
                    )
            except User.DoesNotExist:
                pass
        return data

    def get_active_guarantees_count(self, obj):
        return obj.active_guarantees_count()

    def get_committed_amount(self, obj):
        return float(obj.committed_guarantee_amount)

    def get_available_amount(self, obj):
        return float(obj.available_capacity())

    def get_has_reached_limit(self, obj):
        count = obj.active_guarantees_count()
        return count >= obj.max_active_guarantees

    def create(self, validated_data):
        member_no = validated_data.pop("member_no")
        member = User.objects.get(member_no=member_no)

        total_savings = SavingsAccount.objects.filter(member=member).aggregate(
            total=models.Sum("balance")
        )["total"] or Decimal("0")

        profile = GuarantorProfile.objects.create(
            member=member,
            max_guarantee_amount=total_savings,
            committed_guarantee_amount=Decimal("0"),
            **validated_data,
        )
        return profile
