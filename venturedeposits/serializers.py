from rest_framework import serializers

from venturedeposits.models import VentureDeposit
from ventureaccounts.models import VentureAccount
from paymentaccounts.models import PaymentAccount


class VentureDepositSerializer(serializers.ModelSerializer):
    venture_account = serializers.SlugRelatedField(
        queryset=VentureAccount.objects.all(), slug_field="account_number"
    )
    deposited_by = serializers.CharField(
        source="deposited_by.member_no", read_only=True
    )
    payment_method = serializers.SlugRelatedField(
        slug_field="name", queryset=PaymentAccount.objects.all()
    )

    class Meta:
        model = VentureDeposit
        fields = (
            "venture_account",
            "deposited_by",
            "amount",
            "currency",
            "payment_method",
            "identity",
            "created_at",
            "updated_at",
            "reference",
        )


class BulkVentureDepositSerializer(serializers.Serializer):
    deposits = VentureDepositSerializer(many=True)
