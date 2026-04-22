# Bulk Loan Application Upload Instructions

This endpoint allows administrators to create multiple loan applications and their corresponding active loan accounts in a single batch.

## CSV Format

Your CSV file should have the following headers:

| Column | Description | Mandatory | Possible Values |
|--------|-------------|-----------|-----------------|
| Member No | Unique member identifier | Yes | String (e.g., "SCS001") |
| Product Name | Exact name of the loan product | Yes | String (e.g., "Emergency Loan") |
| Requested Amount | Principal amount requested | Yes | Decimal (e.g., 50000.00) |
| Calculation Mode | How the loan is calculated | Yes | `fixed_term` or `fixed_payment` |
| Term Months | Repayment period in months | Conditional | Required if `fixed_term` |
| Monthly Payment | Desired periodic payment | Conditional | Required if `fixed_payment` |
| Repayment Frequency | Frequency of installments | Yes | `daily`, `weekly`, `biweekly`, `monthly`, `quarterly`, `annually` |
| Start Date | Date of loan graduation | Yes | Date (YYYY-MM-DD) |

## Important Notes

1.  **Partial Success**: Unlike other bulk tools, this system uses a "Graceful Failure" strategy. If one row has an error (e.g., invalid member ID), the rest of the valid rows will still be processed.
2.  **Automated Approval**: All applications created via this tool are automatically moved to "Approved" status, and an "Active" Loan Account is generated immediately.
3.  **Projections**: The system automatically calculates projections (interest, schedules, fees) based on the product's interest rate and method.
