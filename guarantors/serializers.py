from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import models
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from mwandamzeduapi.settings import MEMBER_PERIOD
from guarantors.models import GuarantorProfile
from guaranteerequests.models import GuaranteeRequest
from savings.models import SavingsAccount

User = get_user_model()


class GuarantorProfileSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    member_no = serializers.CharField(write_only=True)  # Accept input

    active_guarantees_count = serializers.SerializerMethodField()
    committed_amount = serializers.SerializerMethodField()
    max_guarantee_amount = serializers.SerializerMethodField()
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
            "max_guarantee_amount",
            "has_reached_limit",
            "reference",
            "created_at",
            "updated_at",
        )

    def validate(self, data):
        if data.get("is_eligible"):
            member_no = data.get("member_no")
            if not member_no:
                raise serializers.ValidationError("Member number is required")

            try:
                member = User.objects.get(member_no=member_no)
            except User.DoesNotExist:
                raise serializers.ValidationError("Member not found")

            months = int(MEMBER_PERIOD)
            required_date = timezone.now() - relativedelta(months=months)
            if member.created_at > required_date:
                raise serializers.ValidationError(
                    f"Member must be at least {months} months old"
                )

        return data

    def get_active_guarantees_count(self, obj):
        return GuaranteeRequest.objects.filter(guarantor=obj, status="Accepted").count()

    def get_committed_amount(self, obj):
        total = GuaranteeRequest.objects.filter(
            guarantor=obj, status="Accepted"
        ).aggregate(total=models.Sum("guaranteed_amount"))["total"]
        return float(total or 0)

    def get_max_guarantee_amount(self, obj):
        # This should be the total savings account balance less committed amount
        total_savings = SavingsAccount.objects.filter(member=obj.member).aggregate(
            total=models.Sum("balance")
        )["total"]
        committed_amount = self.get_committed_amount(obj)
        total_savings = total_savings - committed_amount
        return float(total_savings or 0)

    def get_has_reached_limit(self, obj):
        return self.get_active_guarantees_count(obj) >= obj.max_active_guarantees

    def create(self, validated_data):
        member_no = validated_data.pop("member_no")
        member = User.objects.get(member_no=member_no)
        return GuarantorProfile.objects.create(member=member, **validated_data)
