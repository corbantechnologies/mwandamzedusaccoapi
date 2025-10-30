from rest_framework import serializers

from savingtypes.models import SavingType
from savings.models import Saving


class SavingSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
    account_type = serializers.SlugRelatedField(
        queryset=SavingType.objects.all(), slug_field="name"
    )


    class Meta:
        model = Saving
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
        )