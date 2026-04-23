# Bulk Fee Type Upload Instructions

This endpoint allows you to create multiple Fee Types at once using a CSV file.

## CSV Format

Your CSV file should have the following headers:

| Column | Description | Mandatory | Possible Values |
|--------|-------------|-----------|-----------------|
| Name | The unique name of the fee type | Yes | String (e.g., "Registration Fee") |
| Amount | The cost of the fee | Yes | Decimal (e.g., 1000.00) |
| GL Account Name | The EXACT name of the GL Account for this fee | Yes | String (e.g., "MEMBER ENTRANCE FEES (REVENUE)") |
| Is Everyone | Whether to apply this fee to all members automatically | No | True/False (Default: False) |
| Can Exceed Limit | Whether the fee can exceed a pre-defined limit | No | True/False (Default: False) |

## Important Notes

1.  **GL Account Name**: This MUST match exactly the name of an existing GL Account in the system.
2.  **Is Everyone**: If set to `True`, the system will automatically create `FeeAccount` records for ALL active members in the SACCO.
3.  **Uniqueness**: The `Name` must be unique across all Fee Types.
