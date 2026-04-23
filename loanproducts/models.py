from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from glaccounts.models import GLAccount

User = get_user_model()


class LoanProduct(UniversalIdModel, TimeStampedModel, ReferenceModel):
    """
    - Used to create different loan products.
    - Interest is on default reducing balance
    """

    INTEREST_PERIOD_CHOICES = [
        ("Daily", "Daily"),
        ("Weekly", "Weekly"),
        ("Monthly", "Monthly"),
        ("Annually", "Annually"),
    ]

    INTEREST_METHOD_CHOICES = [
        ("Flat", "Flat-rate"),
        ("Reducing", "Reducing (Diminishing) Balance"),
    ]

    CALCULATION_SCHEDULE_CHOICES = [
        ("Fixed", "Fixed Calendar (e.g., 1st of month)"),
        (
            "Relative",
            "Relative to Loan Start Date",
        ),  # should be the first month after the loan start date. Should the start date be the same as the loan start date?
        ("Flexible", "Custom/Flexible Schedule"),
    ]
    name = models.CharField(max_length=500, unique=True)
    interest_method = models.CharField(
        max_length=20,
        choices=INTEREST_METHOD_CHOICES,
        default="Reducing",
        help_text="Defines how interest is calculated (Flat-rate or Reducing Balance).",
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )
    processing_fee = models.DecimalField(
        # it is a percentage charged on the loan amount
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        default=2.00,
    )
    interest_period = models.CharField(
        max_length=50,
        choices=INTEREST_PERIOD_CHOICES,
        default="Monthly",
        help_text="How interest is calculated",
    )
    calculation_schedule = models.CharField(
        max_length=20,
        choices=CALCULATION_SCHEDULE_CHOICES,
        default="Relative",
        help_text="Defines when interest is calculated (fixed calendar, loan start date, or custom).",
    )
    is_active = models.BooleanField(default=True)
    # ASSET: Tracks the Principal raw amount lent out
    gl_principal_asset = models.ForeignKey(
        GLAccount,
        on_delete=models.PROTECT,
        related_name="loan_principal_assets",
        null=True,
        blank=True,
    )
    # REVENUE: Tracks the actual profit recognized today
    gl_interest_revenue = models.ForeignKey(
        GLAccount,
        on_delete=models.PROTECT,
        related_name="loan_interest_income",
        null=True,
        blank=True,
    )
    # REVENUE/INCOME: Tracks penalties
    gl_penalty_revenue = models.ForeignKey(
        GLAccount,
        on_delete=models.PROTECT,
        related_name="loan_penalty_income",
        null=True,
        blank=True,
    )
    # REVENUE: Tracks the one-time processing fee income
    gl_processing_fee_revenue = models.ForeignKey(
        GLAccount,
        on_delete=models.PROTECT,
        related_name="loan_processing_fee_income",
        null=True,
        blank=True,
    )

    # TODO:
    # Add limits to terms for some products: instant limited to 3 months, etc
    # Add limits to principal for some products: instant limited to 10,000, etc
    # Add limits to loan amounts for some products: instant limited to 50,000, etc

    class Meta:
        verbose_name = "Loan Product"
        verbose_name_plural = "Loan Products"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.interest_rate}% - {self.interest_period} - {self.calculation_schedule}"
