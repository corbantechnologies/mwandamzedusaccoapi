# Fee Payments Bulk Operations Guide

This guide explains how to bulk upload or create fee payments in the SACCO system using either a JSON payload or a CSV file upload.

## 1. JSON Array Creation

**Endpoint:** `/api/v1/feepayments/bulk/create/`
**Method:** `POST`

### Payload Structure
Send a JSON payload containing a `fee_payments` array. Refer to `payload.json` in this directory for an example.

**Field Definitions:**
- `fee_account` (String, Required): The account number of the fee account (e.g., "FEE-001-ADMISSION").
- `amount` (Decimal String, Required): The amount to pay.
- `payment_method` (String, Optional): The name of the payment method (e.g., "Cash", "M-Pesa").

---

## 2. CSV File Upload

**Endpoint:** `/api/v1/feepayments/bulk/upload/`
**Method:** `POST` (Multipart/Form-Data)

### Obtaining the Template
To ensure you have the correct format, download a template pre-filled with active fee accounts that have outstanding balances from:
**Endpoint:** `/api/v1/feepayments/bulk/template/` (Method: `GET`)

### File Structure
The template will have the following columns:
1. `Member Name` (For reference, ignored during upload)
2. `Fee Type` (For reference, ignored during upload)
3. `Fee Account Number` (Required)
4. `Amount` (Required - Fill this for each account receiving a payment)
5. `Payment Method` (Optional - Defaults to "Cash")

---

### Tracking & Logs
Every successful or partially successful bulk action creates a `BulkTransactionLog` record for audit purposes.
- Check `success_count` and `error_count` in the response to verify results.
- For CSV uploads, the original file is stored in Cloudinary for accountability.
- Successful payments trigger immediate accounting logic, updating the `FeeAccount` balances and posting entries to the General Ledger.
