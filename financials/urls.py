# financials/urls.py
from django.urls import path
from financials.views import (
    TrialBalanceView,
    BalanceSheetView,
    PnLStatementView,
    CashBalanceView,
)

urlpatterns = [
    path("trial-balance/", TrialBalanceView.as_view(), name="trial-balance"),
    path("balance-sheet/", BalanceSheetView.as_view(), name="balance-sheet"),
    path("pnl/", PnLStatementView.as_view(), name="pnl-statement"),
    path("cash-balance/", CashBalanceView.as_view(), name="cash-balance"),
]
