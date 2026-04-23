# Bulk Existing Loan Upload Instructions

This endpoint allows you to migrate multiple existing loans from a legacy system using a CSV file.

## CSV Format

Your CSV file should have the following headers:

| Column | Description | Mandatory | Possible Values |
|--------|-------------|-----------|-----------------|
| Member No | The unique ID/Member Number of the member | Yes | String (e.g., "S-001") |
| Principal | The outstanding principal balance at adoption | Yes | Decimal (e.g., 50000.00) |
| GL Principal Asset | The EXACT name of the GL Principal Asset account | Yes | String (e.g., "LOAN PORTFOLIO (ASSET)") |
| GL Penalty Revenue | The EXACT name of the GL Penalty Revenue account | Yes | String (e.g., "LOAN PENALTIES (REVENUE)") |
| GL Interest Revenue | The EXACT name of the GL Interest Revenue account | Yes | String (e.g., "LOAN INTEREST (REVENUE)") |
| Status | Current status of the loan | No | Active, Closed, Defaulted (Default: Active) |
| Payment Method | Preferred payment method name | Yes | String (e.g., "MPESA TILL") |
| Total Amount Paid | Cumulative principal paid to date | No | Decimal (Default: 0.00) |
| Total Interest Paid | Cumulative interest paid to date | No | Decimal (Default: 0.00) |
| Total Penalties Paid| Cumulative penalties paid to date | No | Decimal (Default: 0.00) |

## Important Notes

1.  **Account Mapping**: All GL Account and Payment Method names must match exactly what is in the SACCO system.
2.  **Identifiers**: `Member No` must belong to an existing active member in the system.
3.  **Outstanding Balance**: The system automatically calculates `Outstanding Balance = Principal - Total Amount Paid`.
