from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from savingtypes.models import SavingType

class SavingTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(validators=[UniqueValidator(queryset=SavingType.objects.all())])

    class Meta:
        model = SavingType
        fields = (
            "name",
            "interest_rate",
            "is_active",
            "created_at",
            "updated_at",
            "reference",
        )