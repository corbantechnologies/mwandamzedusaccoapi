# Saving Types Bulk Operations Guide

This guide explains how to bulk import/create Saving Types in the SACCO system using either a JSON payload or a CSV file upload.

> [!IMPORTANT]
> When a Saving Type is created successfully, the system automatically loops through all current active Members and generates a `SavingsAccount` under their profile for this new Saving Type.

## 1. JSON Array Creation

**Endpoint:** `/api/v1/savingtypes/bulk/create/`
**Method:** `POST`

### Payload Structure
Send a JSON payload containing a `saving_types` array. Refer to `payload.json` in this directory.

**Field Definitions:**
- `name` (String, Required): The name of the saving type (e.g., "Normal Deposits"). Must be unique.
- `gl_account` (String, Required): The exact **GL Account Name** (e.g., "Member Deposits Payable"). The backend maps this inherently.
- `interest_rate` (Decimal String, Optional): The interest percentage. Defaults to "0.00".
- `can_guarantee` (Boolean, Optional): Whether this savings account type can be used as loan collateral. Defaults to `true`.
- `is_active` (Boolean, Optional): Defaults to `true`.

---

## 2. CSV File Upload

**Endpoint:** `/api/v1/savingtypes/bulk/upload/`
**Method:** `POST` (Multipart/Form-Data)

### Obtaining the Template
To get a fresh template with the required headers:
**Endpoint:** `/api/v1/savingtypes/bulk/template/` (Method: `GET`)

### File Structure
Upload your CSV using the `file` form key.

Expected Column Headers (Case Sensitive):
1. `Name`
2. `Interest Rate`
3. `GL Account Name`
4. `Can Guarantee` (Accepts: true, 1, yes, false, 0, no)
5. `Is Active`

### Tracking & Logs
Every bulk entry logs an immutable `BulkTransactionLog`:
- Prefix: `SAVINGTYPE-BULK-JSON-YYYYMMDD` (for JSON array creates)
- Prefix: `SAVINGTYPE-BULK-YYYYMMDD` (for CSV uploads linked with Cloudinary auditing)
