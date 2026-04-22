# financials/views.py
from datetime import date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from financials.reports import (
    get_trial_balance,
    get_balance_sheet,
    get_pnl_statement,
    get_cash_balances,
)


def _parse_date(date_str, param_name):
    """Parse a YYYY-MM-DD string into a date object. Returns (date, error_str)."""
    try:
        return date.fromisoformat(date_str), None
    except (ValueError, TypeError):
        return None, f"'{param_name}' must be in YYYY-MM-DD format."


class TrialBalanceView(APIView):
    """
    GET /api/v1/financials/trial-balance/

    Query params:
        as_of_date (optional): YYYY-MM-DD  — defaults to today
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        as_of_date = None
        raw = request.query_params.get("as_of_date")
        if raw:
            as_of_date, err = _parse_date(raw, "as_of_date")
            if err:
                return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        data = get_trial_balance(as_of_date=as_of_date)
        return Response(data)


class BalanceSheetView(APIView):
    """
    GET /api/v1/financials/balance-sheet/

    Query params:
        as_of_date (optional): YYYY-MM-DD  — defaults to today
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        as_of_date = None
        raw = request.query_params.get("as_of_date")
        if raw:
            as_of_date, err = _parse_date(raw, "as_of_date")
            if err:
                return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        data = get_balance_sheet(as_of_date=as_of_date)
        return Response(data)


class PnLStatementView(APIView):
    """
    GET /api/v1/financials/pnl/

    Query params (both optional, default to current month):
        start_date: YYYY-MM-DD
        end_date:   YYYY-MM-DD
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = None
        end_date = None

        raw_start = request.query_params.get("start_date")
        raw_end = request.query_params.get("end_date")

        if raw_start:
            start_date, err = _parse_date(raw_start, "start_date")
            if err:
                return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        if raw_end:
            end_date, err = _parse_date(raw_end, "end_date")
            if err:
                return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        if start_date and end_date and start_date > end_date:
            return Response(
                {"error": "'start_date' cannot be later than 'end_date'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = get_pnl_statement(start_date=start_date, end_date=end_date)
        return Response(data)


class CashBalanceView(APIView):
    """
    GET /api/v1/financials/cash-balance/

    Query params:
        as_of_date (optional): YYYY-MM-DD  — defaults to today
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        as_of_date = None
        raw = request.query_params.get("as_of_date")
        if raw:
            as_of_date, err = _parse_date(raw, "as_of_date")
            if err:
                return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        data = get_cash_balances(as_of_date=as_of_date)
        return Response(data)
