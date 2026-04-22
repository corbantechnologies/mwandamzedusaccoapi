# GL Accounts Bulk Operations Guide

This guide explains how to bulk import General Ledger (GL) Accounts into the SACCO system using either a JSON payload or a CSV file upload.

## 1. JSON Array Creation

**Endpoint:** `/api/v1/glaccounts/bulk/create/`
**Method:** `POST`

### Payload Structure
Send a JSON payload containing an `accounts` array. Refer to `payload.json` in this directory for an example.

**Field Definitions:**
- `name` (String, Required): The textual name of the GL Account (e.g., "M-Pesa Paybill"). Must be unique.
- `code` (String, Required): The numerical/alphanumeric code matching the chart of accounts. Must be unique.
- `category` (String, Required): Must be exactly one of: `ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`.
- `is_active` (Boolean, Optional): Defaults to `true`.
- `is_current_account` (Boolean, Optional): Defaults to `true`.

### Note on Balances
For all GL Account bulk operations (JSON and CSV), the system will **automatically default the starting balance to `0.00`**. You do not need to provide a balance field. Establishing opening balances should be handled subsequently through Journal Batch entries.

---

## 2. CSV File Upload

**Endpoint:** `/api/v1/glaccounts/bulk/upload/`
**Method:** `POST` (Multipart/Form-Data)

### Obtaining the Template
To ensure you have the correct column headers, you can download an empty template from:
**Endpoint:** `/api/v1/glaccounts/bulk/template/` (Method: `GET`)

### File Structure
When uploading, provide the CSV under the `file` form key.

Expected Column Headers (Case Sensitive):
1. `Name`
2. `Code`
3. `Category`
4. `Is Active` (Accepts: true, 1, yes, y, false, 0, no, n)
5. `Is Current Account` 

### Tracking & Logs
Every successful or partially successful bulk action creates a `BulkTransactionLog` record. 
- Prefix: `GL-BULK-JSON-YYYYMMDD` (for array creates)
- Prefix: `GL-BULK-YYYYMMDD` (for CSV uploads)

If using CSV uploads, the original file is mirrored to Cloudinary for strict auditing, and its `secure_url` is saved directly onto the `BulkTransactionLog` instance.
