from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel

User = get_user_model()


class LoanProduct(UniversalIdModel, TimeStampedModel, ReferenceModel):
    """
    - Used to create different loan products.
    - Interest is on default flat rate
    """

    INTEREST_PERIOD_CHOICES = [
        ("Daily", "Daily"),
        ("Weekly", "Weekly"),
        ("Monthly", "Monthly"),
        ("Annually", "Annually"),
    ]

    CALCULATION_SCHEDULE_CHOICES = [
        ("Fixed", "Fixed Calendar (e.g., 1st of month)"),
        ("Relative", "Relative to Loan Start Date"),
        ("Flexible", "Custom/Flexible Schedule"),
    ]
    name = models.CharField(max_length=500, unique=True)
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
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

    class Meta:
        verbose_name = "Loan Product"
        verbose_name_plural = "Loan Products"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.interest_rate}% - {self.interest_period} - {self.calculation_schedule}"
