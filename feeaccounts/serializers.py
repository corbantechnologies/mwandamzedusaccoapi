from rest_framework import serializers
from django.contrib.auth import get_user_model

from feeaccounts.models import FeeAccount
from feetypes.models import FeeType

User = get_user_model()


class FeeAccountSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    fee_type = serializers.SlugRelatedField(
        slug_field="name", queryset=FeeType.objects.all()
    )

    fee_type_details = serializers.SerializerMethodField()

    def get_fee_type_details(self, obj):
        return {
            "name": obj.fee_type.name,
            "amount": obj.fee_type.amount,
            "is_everyone": obj.fee_type.is_everyone,
            "can_exceed_limit": obj.fee_type.can_exceed_limit,
        }

    class Meta:
        model = FeeAccount
        fields = (
            "id",
            "member",
            "fee_type",
            "account_number",
            "amount_paid",
            "outstanding_balance",
            "is_paid",
            "created_at",
            "updated_at",
            "reference",
            "fee_type_details",
        )
