from rest_framework import serializers

from savingtypes.models import SavingType
from savings.models import SavingsAccount
from savingsdeposits.serializers import SavingsDepositSerializer


class SavingSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    account_type = serializers.SlugRelatedField(
        queryset=SavingType.objects.all(), slug_field="name"
    )
    account_type_details = serializers.SerializerMethodField()
    deposits = SavingsDepositSerializer(many=True, read_only=True)

    class Meta:
        model = SavingsAccount
        fields = (
            "member",
            "account_type",
            "account_number",
            "balance",
            "is_active",
            "identity",
            "reference",
            "created_at",
            "updated_at",
            "account_type_details",
            "deposits",
        )

    def get_account_type_details(self, obj):
        return {
            "name": obj.account_type.name,
            "interest_rate": obj.account_type.interest_rate,
            "is_active": obj.account_type.is_active,
        }
