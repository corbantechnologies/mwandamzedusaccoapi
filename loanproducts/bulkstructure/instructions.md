# Loan Products Bulk Operations Guide

This guide explains how to bulk import/create Loan Products into the SACCO system using either a JSON payload or a CSV file upload.

> [!NOTE]
> Setting up Loan Products requires mapping to **four distinct GL Accounts**. The system makes this easy by allowing you to use the **GL Account Name** directly instead of hunting down complex account codes.

## 1. JSON Array Creation

**Endpoint:** `/api/v1/loanproducts/bulk/create/`
**Method:** `POST`

### Payload Structure
Send a JSON payload containing a `loan_products` array. Refer to `payload.json` in this directory for a complete example.

**Field Definitions:**
- `name` (String, Required): The name of the loan product (e.g., "Development Loan"). Must be unique.
- `interest_method` (String, Optional): How interest is calculated. Accepts `Reducing` or `Flat` (defaults to `Reducing`).
- `interest_rate` (Decimal String, Optional): The interest percentage rate. Defaults to "0.00".
- `processing_fee` (Decimal String, Optional): The percentage limit charged as a processing fee. Defaults to "0.00".
- `interest_period` (String, Optional): Choose from `Daily`, `Weekly`, `Monthly`, `Annually`. Defaults to `Monthly`.
- `calculation_schedule` (String, Optional): Choose from `Fixed`, `Relative`, `Flexible`. Defaults to `Fixed`.
- `gl_principal_asset` (String, Optional): GL Account Name handling the principal loan asset outlays.
- `gl_interest_revenue` (String, Optional): GL Account Name recognizing actual profit/interest.
- `gl_penalty_revenue` (String, Optional): GL Account Name tracking penalty charges.
- `gl_processing_fee_revenue` (String, Optional): GL Account Name tracking one-time processing fee revenue.
- `is_active` (Boolean, Optional): Defaults to `true`.

---

## 2. CSV File Upload

**Endpoint:** `/api/v1/loanproducts/bulk/upload/`
**Method:** `POST` (Multipart/Form-Data)

### Obtaining the Template
To ensure you have the expected column headers, download an empty template from:
**Endpoint:** `/api/v1/loanproducts/bulk/template/` (Method: `GET`)

### File Structure
Upload your CSV utilizing the `file` form key.

Expected Column Headers (Case Sensitive):
1. `Name`
2. `Interest Method`
3. `Interest Rate`
4. `Processing Fee`
5. `Interest Period`
6. `Calculation Schedule`
7. `GL Principal Asset`
8. `GL Interest Revenue`
9. `GL Penalty Revenue`
10. `GL Processing Fee Revenue`
11. `Is Active` (Accepts: true, 1, yes, false, 0, no)

### Auto-Correction Under The Hood
If users type "Reducing Balance" instead of exactly "Reducing", or "Flat-Rate" instead of "Flat" in the CSV, the system handles sanitization automatically.

### Tracking & Logs
Every bulk entry logs an immutable `BulkTransactionLog`:
- Prefix: `LOANPRODUCT-BULK-JSON-YYYYMMDD` (for array creates)
- Prefix: `LOANPRODUCT-BULK-YYYYMMDD` (for CSV uploads tied to Cloudinary)
