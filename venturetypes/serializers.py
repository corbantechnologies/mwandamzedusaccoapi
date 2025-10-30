from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from venturetypes.models import VentureType


class VentureTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        validators=[UniqueValidator(queryset=VentureType.objects.all())]
    )

    class Meta:
        model = VentureType
        fields = (
            "name",
            "interest_rate",
            "is_active",
            "created_at",
            "updated_at",
            "reference",
        )
