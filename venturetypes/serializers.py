from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from venturetypes.models import VentureType
from glaccounts.models import GLAccount


class VentureTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        validators=[UniqueValidator(queryset=VentureType.objects.all())]
    )
    gl_account = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )

    class Meta:
        model = VentureType
        fields = (
            "name",
            "interest_rate",
            "is_active",
            "gl_account",
            "created_at",
            "updated_at",
            "reference",
        )
