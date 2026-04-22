# Universal Bulk Transaction Operations Guide

This guide explains how to use the **Universal Bulk Upload** feature to process multiple types of transactions (Savings Deposits, Fee Payments, and Loan Disbursements) in a single file or payload.

---

## 1. Universal CSV File Upload

**Endpoint:** `/api/v1/transactions/bulk/universal/upload/`
**Method:** `POST` (Multipart/Form-Data)

### Obtaining the Pre-filled Template
To make this process as efficient as possible, the system provides a template that includes all actionable accounts.
**Endpoint:** `/api/v1/transactions/bulk/universal/template/` (Method: `GET`)

### File Structure
The template includes:
1. `Member Name` (For reference)
2. `Account Number` (Required - Used to resolve the Savings, Fee, or Loan account)
3. `Transaction Type` (Required - Must be exactly "Savings Deposit", "Fee Payment", or "Loan Disbursement")
4. `Amount` (Required - The decimal amount to process)
5. `Payment Method` (Optional - Defaults to "Cash")

### Automated Actions by Type
- **Savings Deposit**: Creates `SavingsDeposit` + Triggers Accounting + Sends Email.
- **Fee Payment**: Creates `FeePayment` + Triggers Accounting.
- **Loan Disbursement**: Creates `LoanDisbursement` + Updates Application Status to **"Disbursed"** + Triggers Accounting + Sends Email.

---

## 2. JSON Array Creation

**Endpoint:** `/api/v1/transactions/bulk/universal/upload/`
**Method:** `POST`

### Payload Structure
Send a JSON array containing transaction objects. Refer to `payload.json` in this directory for an example.

**Field Definitions:**
- `Transaction Type` (String, Required)
- `Account Number` (String, Required)
- `Amount` (Decimal String/Number, Required)
- `Payment Method` (String, Optional)

---

### Audit Logs & Error Handling
All operations are tracked in the `BulkTransactionLog`.
- The system returns a summary showing `success_count` and `error_count`.
- If a row fails (e.g., account not found or unbalanced), it will be caught in the `errors` array with its row index and the specific validation message.
- The entire process is wrapped in a `transaction.atomic()` block per file upload to ensure database consistency.
