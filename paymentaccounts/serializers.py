from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from paymentaccounts.models import PaymentAccount
from glaccounts.models import GLAccount


class PaymentAccountSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        validators=[UniqueValidator(queryset=PaymentAccount.objects.all())]
    )
    gl_account = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )

    class Meta:
        model = PaymentAccount
        fields = (
            "id",
            "name",
            "gl_account",
            "code",
            "is_active",
            "reference",
            "created_at",
            "updated_at",
        )


class BulkPaymentAccountSerializer(serializers.Serializer):
    accounts = PaymentAccountSerializer(many=True)


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
