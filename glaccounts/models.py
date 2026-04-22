from django.db import models

from accounts.abstracts import ReferenceModel, TimeStampedModel, UniversalIdModel


class GLAccount(ReferenceModel, TimeStampedModel, UniversalIdModel):
    """
    General Ledger Account Model
    """

    CATEGORIES = [
        ("ASSET", "Asset"),  # Bank, M-Pesa, Loan Receivables: 100000-199999
        (
            "LIABILITY",
            "Liability",
        ),  # Loans Payable, Deposits Payable, Member Savings, Ventures: 200000-299999
        ("EQUITY", "Equity"),  # Share Capital, Retained Earnings: 300000-399999
        (
            "REVENUE",
            "Revenue",
        ),  # Interest Income, Fees Income, Loan Interest Income: 400000-499999
        ("EXPENSE", "Expense"),  # Interest Expense, Operating Expenses: 500000-599999
    ]

    name = models.CharField(max_length=2505, unique=True)
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Ensure utmost care when setting this code as it will be used for all transactions.",
    )
    category = models.CharField(choices=CATEGORIES, max_length=20)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    # TODO: Add a field for the GL Account current status
    is_current_account = models.BooleanField(default=True)

    class Meta:
        verbose_name = "General Ledger Account"
        verbose_name_plural = "General Ledger Accounts"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["balance"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.category})"
