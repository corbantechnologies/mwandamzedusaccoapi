# Bulk Existing Loan Payment Upload Instructions

This endpoint allows you to migrate multiple installment payments for legacy loans using a CSV file.

## CSV Format

Your CSV file should have the following headers:

| Column | Description | Mandatory | Possible Values |
|--------|-------------|-----------|-----------------|
| Loan Account No | The unique account number of the existing loan | Yes | String (e.g., "EL-2024-001") |
| Repayment Type | The category of the payment | Yes | Regular Repayment, Partial Payment, Loan Clearance, etc. |
| Amount | The monetary value of the payment | Yes | Decimal (e.g., 2500.00) |
| Payment Method | Name of the payment method (Bank, Cash, etc.) | Yes | String (e.g., "CASH AT HAND") |

## Important Notes

1.  **Loan Linking**: The `Loan Account No` MUST belong to a loan already migrated via the Bulk Existing Loan feature.
2.  **Accounting Triggers**: Every payment successfully uploaded will automatically trigger the SACCO ledger updates. This will decrease the `Outstanding Balance` of the related loan and post a journal entry.
3.  **Payment Method**: Ensure the payment method name matches exactly as defined in the Setup.
