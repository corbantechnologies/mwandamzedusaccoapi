from rest_framework import serializers
from loanapplications.models import LoanApplication
from loanproducts.models import LoanProduct
from loanapplications.calculators import flat_rate_projection
from decimal import Decimal
from datetime import date

from guarantors.models import GuarantorProfile
from guaranteerequests.models import GuaranteeRequest


class LoanApplicationSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_number", read_only=True)
    product = serializers.SlugRelatedField(
        slug_field="name",
        queryset=LoanProduct.objects.filter(is_active=True),
    )
    requested_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=1
    )
    start_date = serializers.DateField(default=date.today)
    projection = serializers.SerializerMethodField()

    class Meta:
        model = LoanApplication
        fields = (
            "id",
            "member",
            "product",
            "requested_amount",
            "term_months",
            "repayment_frequency",
            "start_date",
            "status",
            "projection",
            "created_at",
            "reference",
        )
        read_only_fields = ("status", "projection", "created_at", "reference")

    def get_projection(self, obj):
        return obj.projection_snapshot

    def get_can_submit(self, obj):
        from guarantors.rules import validate_guarantee_rules

        ok, _ = validate_guarantee_rules(obj)
        return ok

    # ------Projection Helpers------
    def _should_recalculate_projection(self, validated_data, instance):
        fields_to_check = [
            "requested_amount",
            "term_months",
            "repayment_frequency",
            "start_date",
            "product",
        ]
        return any(
            validated_data.get(field) != getattr(instance, field)
            for field in fields_to_check
            if field in validated_data
        )

    def _generate_projection(self, validated_data, instance):
        # Use updated product if provided, else fall back to instance
        product = validated_data.get("product", instance.product)
        principal = Decimal(
            validated_data.get("requested_amount", instance.requested_amount)
        )
        term_months = validated_data.get("term_months", instance.term_months)
        frequency = validated_data.get(
            "repayment_frequency", instance.repayment_frequency
        ).lower()
        start_date = validated_data.get("start_date", instance.start_date)

        return flat_rate_projection(
            principal=principal,
            annual_rate=product.interest_rate,
            term_months=term_months,
            start_date=start_date,
            repayment_frequency=frequency,
        )

    # ------Create------
    def create(self, validated_data):
        # Extract guarantee requests from raw data
        guarantee_data = self.context["request"].data.get("guarantee_requests", [])

        # Generate projection
        projection = self._generate_projection(validated_data, None)

        # Create loan application instance
        instance = LoanApplication.objects.create(
            **validated_data, projection_snapshot=projection, status="In Progress"
        )

        # Create guarantee requests
        for item in guarantee_data:
            guarantor = GuarantorProfile.objects.get(
                member__member_no=item["guarantor"]
            )
            GuaranteeRequest.objects.create(
                loan_application=instance,
                guarantor=guarantor,
                guaranteed_amount=item["guaranteed_amount"],
            )
        return instance

    def update(self, instance, validated_data):
        # Handle guarantee requests (optional on update)
        guarantee_data = self.context["request"].data.get("guarantee_requests")
        if guarantee_data is not None:
            # Delete old, create new
            instance.guarantee_requests.all().delete()
            for item in guarantee_data:
                guarantor = GuarantorProfile.objects.get(
                    member__member_number=item["guarantor"]
                )
                GuaranteeRequest.objects.create(
                    loan_application=instance,
                    guarantor=guarantor,
                    guaranteed_amount=item["guaranteed_amount"],
                )
                
        # Only recalculate if a relevant field changed
        if self._should_recalculate_projection(validated_data, instance):
            projection = self._generate_projection(validated_data, instance)
            validated_data["projection_snapshot"] = projection
            # Auto-set status to In Progress on recalculation
            if "status" not in validated_data:
                validated_data["status"] = "In Progress"

        # Apply updates
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
