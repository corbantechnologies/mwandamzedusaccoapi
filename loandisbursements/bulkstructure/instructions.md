# Loan Disbursements Bulk Operations Guide

This guide explains how to bulk process loan disbursements for approved loan applications using either a JSON payload or a CSV file upload.

## 1. JSON Array Creation

**Endpoint:** `/api/v1/loandisbursements/bulk/create/`
**Method:** `POST`

### Payload Structure
Send a JSON payload containing a `disbursements` array. Refer to `payload.json` in this directory for an example.

**Field Definitions:**
- `loan_account` (String, Required): The account number of the loan account to be disbursed (e.g., "LOAN-001-2024").
- `amount` (Decimal String, Required): The amount to disburse. Typically matches the loan principal.
- `payment_method` (String, Optional): The name of the payment method (e.g., "Bank Transfer", "M-Pesa").

---

## 2. CSV File Upload

**Endpoint:** `/api/v1/loandisbursements/bulk/upload/`
**Method:** `POST` (Multipart/Form-Data)

### Obtaining the Template
To make the process concise, the system provides a template pre-filled with all loans currently in "Approved" status.
**Endpoint:** `/api/v1/loandisbursements/bulk/template/` (Method: `GET`)

### File Structure
The template includes:
1. `Member Name` (For reference)
2. `Loan Account Number` (Required)
3. `Principal Amount` (Pre-filled, Required)
4. `Payment Method` (Optional - Fill this to specify how funds were sent)

### Automated Actions
Upon successful upload/creation:
- A `LoanDisbursement` record is created.
- The corresponding `LoanApplication` status is automatically updated to **"Disbursed"**.
- The `LoanAccount` status progresses through the "Funded" and "Active" states.
- The **General Ledger (GL)** accounting entries are automatically posted (Debit Loan Asset / Credit Bank).
- A disbursement notification email is sent to the member if they have an email address on file.

---

### Audit Logs
All bulk operations are tracked in the `BulkTransactionLog`.
- CSV uploads are stored on Cloudinary for permanent audit records.
- Check the API response for `success_count` and detailed `errors` per row.
