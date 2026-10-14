# Proposal

## Why

Owners need to know what they earned, spent, and owe (goals.md section 7) without a full accounting system. Sales, payments, purchases, and stock costs already exist; this change adds expenses, supplier payments, a cash/bank movement view, and consistent profit calculations that reports can reuse.

## What Changes

- Add operating expenses with category (seeded: rent, utilities, salaries, equipment, maintenance, marketing, delivery, other), amount, date, payment status, payment account, description, and responsible user; corrections by reversal.
- Add supplier payments allocated to one or more posted payables of a supplier, including optional payment at receipt posting; corrections by reversal.
- Add money accounts (seeded: Cash drawer, Bank) mapped from payment methods, and a cash/bank movement ledger combining customer payments, refunds, supplier payments, paid expenses, and authorized cash adjustments, with recorded (not reconciled) balances.
- Add a financial summary service for a date range: gross sales, discounts, refunds, taxes, net sales, COGS, gross profit, expenses, estimated operating profit, plus a per-order income listing.
- Add Expenses page, supplier payment flow on the Suppliers page, and a Cash and Bank page.

## Capabilities

### New Capabilities

- `expenses`: operating expense recording, categories, payment status, and reversal.
- `supplier-payments`: paying supplier payables, allocation, outstanding balances, and reversal.
- `cash-movements`: money accounts and the ledger of recorded money in and out.
- `financial-summary`: period income, COGS, and profit figures derived from source transactions.

### Modified Capabilities

None.

## Impact

- Backend: new `backend/app/modules/accounting/`; migration for `expense_categories`, `expenses`, `supplier_payments`, `supplier_payment_allocations`, `money_accounts`, `cash_movements`; `payment_methods.account_id`; receipt posting accepts optional immediate payment; permissions `expenses:view`, `expenses:manage`, `supplier_payments:manage`, `cash:view`, `cash:adjust`, `finance:view`.
- Frontend: `routes/_layout/expenses.tsx`, `routes/_layout/cash.tsx`, supplier payment dialog, payment option on receipt posting.
- Requires `suppliers-stock-receipts`, `payments-refunds`, `recipes-auto-deduction`.
