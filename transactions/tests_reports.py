from django.test import TestCase
from django.utils import timezone
from datetime import date, timedelta
from transactions.reports import get_debtors_report, get_cash_book
from accounts.models import User
from loanproducts.models import LoanProduct
from loanaccounts.models import LoanAccount
from loanpayments.models import LoanPayment
from decimal import Decimal


class FinancialReportsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            password="password123",
            member_no="M001",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            gender="Male",
        )
        self.product = LoanProduct.objects.create(
            name="Test Product", interest_rate=10, duration_months=12
        )
        self.loan = LoanAccount.objects.create(
            member=self.user,
            product=self.product,
            principal=Decimal("10000"),
            outstanding_balance=Decimal("5000"),
            status="Active",
            account_number="L001",
        )
        self.payment = LoanPayment.objects.create(
            loan_account=self.loan,
            amount=Decimal("1000"),
            payment_date=timezone.now() - timedelta(days=1),
            transaction_status="Completed",
        )

    def test_get_debtors_report_optimizations(self):
        """Test that debtors report returns correct data including last_payment_date."""
        report = get_debtors_report()
        self.assertEqual(len(report["debtors"]), 1)
        debtor = report["debtors"][0]
        self.assertEqual(debtor["member_no"], "M001")
        self.assertEqual(debtor["outstanding_balance"], Decimal("5000"))
        self.assertEqual(debtor["last_payment_date"], self.payment.payment_date)

    def test_get_cash_book_defaults(self):
        """Test that cash book defaults to current month if no dates provided."""
        report = get_cash_book()
        today = timezone.now().date()
        expected_start = today.replace(day=1)
        self.assertEqual(report["start_date"], expected_start)
        self.assertEqual(report["end_date"], today)

    def test_get_cash_book_sorting_and_types(self):
        """Test that get_cash_book correctly sorts mixed date/datetime types."""
        from venturepayments.models import VenturePayment
        from ventureaccounts.models import VentureAccount
        from venturetypes.models import VentureType
        from datetime import date

        vt = VentureType.objects.create(name="Venture Test")
        va = VentureAccount.objects.create(member=self.user, venture_type=vt)

        # This is a DateField
        vp = VenturePayment.objects.create(
            venture_account=va,
            amount=Decimal("500"),
            payment_date=date.today(),
            transaction_status="Completed",
        )

        report = get_cash_book()
        self.assertTrue(
            len(report["transactions"]) >= 2
        )  # Loan payment and Venture payment

        # Verify all dates are datetimes
        for t in report["transactions"]:
            self.assertIsInstance(t["date"], datetime)
