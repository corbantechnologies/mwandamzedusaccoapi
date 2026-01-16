from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from savingtypes.models import SavingType


class SavingTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        validators=[UniqueValidator(queryset=SavingType.objects.all())]
    )
    can_guarantee = serializers.BooleanField(default=True)

    class Meta:
        model = SavingType
        fields = (
            "name",
            "interest_rate",
            "can_guarantee",
            "is_active",
            "created_at",
            "updated_at",
            "reference",
        )
