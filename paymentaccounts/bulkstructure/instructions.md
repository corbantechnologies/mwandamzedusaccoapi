# Payment Accounts Bulk Operations Guide

This guide explains how to bulk import Payment Accounts into the SACCO system using either a JSON payload or a CSV file upload.

> [!NOTE]
> To make it entirely user-friendly, Payment Accounts link to their underlying GL Account using the **GL Account Name** directly, rather than an internal ID or Code. The system handles the matching strictly under the hood.

## 1. JSON Array Creation

**Endpoint:** `/api/v1/paymentaccounts/bulk/create/`
**Method:** `POST`

### Payload Structure
Send a JSON payload containing an `accounts` array. Refer to `payload.json` in this directory for an example.

**Field Definitions:**
- `name` (String, Required): The external/human-readable name for the payment method (e.g., "M-Pesa Paybill 123456"). Must be unique.
- `gl_account` (String, Required): The exact `name` of an already existing GL Account that funds from this method should be mapped to strictly.
- `is_active` (Boolean, Optional): Defaults to `true`.

---

## 2. CSV File Upload

**Endpoint:** `/api/v1/paymentaccounts/bulk/upload/`
**Method:** `POST` (Multipart/Form-Data)

### Obtaining the Template
To ensure you have the correct column headers, download an empty template from:
**Endpoint:** `/api/v1/paymentaccounts/bulk/template/` (Method: `GET`)

### File Structure
When uploading, provide the CSV under the `file` form key.

Expected Column Headers (Case Sensitive):
1. `Name`
2. `GL Account Name`
3. `Is Active` (Accepts: true, 1, yes, y, false, 0, no, n)

### Tracking & Logs
Every successful or partially successful bulk action creates a `BulkTransactionLog` record to enforce an immutable audit trail.
- Prefix: `PAY-BULK-JSON-YYYYMMDD` (for array creates)
- Prefix: `PAY-BULK-YYYYMMDD` (for CSV uploads)

If using CSV uploads, the original file uploaded is mirrored to Cloudinary for strict auditing, and its `secure_url` is saved directly onto the `BulkTransactionLog` instance.
