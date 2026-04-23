# Savings Deposits Bulk Operations Guide

This guide explains how to bulk upload or create savings deposits in the SACCO system using either a JSON payload or a CSV file upload.

## 1. JSON Array Creation

**Endpoint:** `/api/v1/savingsdeposits/bulk/`
**Method:** `POST`

### Payload Structure
Send a JSON payload containing a `deposits` array. Refer to `payload.json` in this directory for an example.

**Field Definitions:**
- `savings_account` (String, Required): The account number of the member's savings account (e.g., "SAV-001-2024").
- `amount` (Decimal String, Required): The amount to deposit. Must be at least 0.01.
- `payment_method` (String, Optional): The name of the payment method (e.g., "Cash", "M-Pesa").
- `description` (String, Optional): A brief note about the deposit.

---

## 2. CSV File Upload

**Endpoint:** `/api/v1/savingsdeposits/bulk/upload/`
**Method:** `POST` (Multipart/Form-Data)

### Obtaining the Template
To ensure you have the correct format, download an empty but pre-filled template containing all active savings accounts from:
**Endpoint:** `/api/v1/savingsdeposits/bulk/template/` (Method: `GET`)

### File Structure
The template will have the following columns:
1. `Member Name` (For reference, ignored during upload)
2. `Account Number` (Required)
3. `Saving Type` (For reference, ignored during upload)
4. `Amount` (Required - Fill this for each account receiving a deposit)
5. `Payment Method` (Optional - Defaults to "Cash")

### Legacy Format Support
The system also supports a horizontal format where each row represents a member and columns are formatted as `{Saving Type Name} Amount` and `{Saving Type Name} Account`.

### Tracking & Logs
Every successful or partially successful bulk action creates a `BulkTransactionLog` record for audit purposes.
- Check `success_count` and `error_count` in the response to verify results.
- For CSV uploads, the original file is stored in Cloudinary for accountability.
