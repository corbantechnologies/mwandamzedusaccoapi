# Journal Batches & Entries Bulk Operations Guide

This guide explains how to bulk upload or create Journal Batches with their respective entries while ensuring strict double-entry balance requirements.

## 1. JSON Array Creation

**Endpoint:** `/api/v1/journalbatches/bulk/create/`
**Method:** `POST`

### Payload Structure
Send a JSON payload containing an array of batch objects. Each batch object MUST contain an `entries` array. Refer to `payload.json` in this directory for examples.

**Field Definitions:**
- `description` (String, Required): A summary of the batch.
- `entries` (Array, Required):
    - `account` (String, Required): The exact NAME of the GL Account.
    - `debit` (Decimal, Required): Only one of debit/credit can be non-zero.
    - `credit` (Decimal, Required): Only one of debit/credit can be non-zero.

**Balance Rule:** For each batch, `sum(debit) - sum(credit)` MUST equal `0`.

---

## 2. CSV File Upload

**Endpoint:** `/api/v1/journalbatches/bulk/upload/`
**Method:** `POST` (Multipart/Form-Data)

### Obtaining the Template
**Endpoint:** `/api/v1/journalbatches/bulk/template/` (Method: `GET`)

### File Structure & Grouping
The system uses the `Batch Identifier` column to group multiple rows into a single batch.
1. `Batch Identifier`: Use the same ID (e.g., "B001") for all entries that belong together.
2. `Batch Description`: Applied to the entire batch.
3. `GL Account Name`: The exact name of the account to post to.
4. `Debit` / `Credit`: Enter the amount.

### Validation & Side Effects
- **Strict Atomicity**: If a single batch in your file is unbalanced, that specific batch will fail, but other balanced batches in the same file will still be processed.
- **Account Balances**: Saving an entry immediately updates the `balance` field on the corresponding `GLAccount` based on its category (Asset, Liability, etc.).

---

### Audit Logs
All bulk operations are tracked in the `BulkTransactionLog`.
- CSV uploads are stored on Cloudinary for permanent audit records.
- Check the API response for `success_count` and detailed `errors` describing which batch was unbalanced or which GL Account name was incorrect.
