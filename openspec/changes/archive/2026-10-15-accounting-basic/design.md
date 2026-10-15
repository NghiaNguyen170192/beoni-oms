# Design

## Context

Payments, refunds, voids (`payments-refunds`), payables (`suppliers-stock-receipts`), and line COGS plus return costs (`recipes-auto-deduction`) already exist. This change adds money-side records and the shared financial calculation.

## Goals / Non-Goals

**Goals:** expenses, supplier payments, and a single `cash_movements` ledger written in the same transaction as each money event; one `financial_summary` function reused by `reporting-dashboard`.

**Non-Goals:** double-entry general ledger, chart of accounts, bank reconciliation, tax filing, payroll, accrual accounting for expenses beyond the expense date.

## Decisions

- **Ledger written by source services.** `payments`, `refunds`, `expenses`, `supplier_payments`, and `cash_adjustments` call `accounting.record_money_movement(...)` (no commit). Payments-refunds code gets a small hook in this change; earlier payments are backfilled by the migration so balances are complete.
- **Expense model:** `expenses` with `status recorded|reversed`, `payment_status paid|unpaid`, `paid_at`, `account_id`. Edits limited to description; financial fields immutable.
- **Supplier payments:** `supplier_payments` + `supplier_payment_allocations(payment_id, payable_id, amount)`; payable `paid_amount` updated under a payable row lock (sorted ids).
- **Receipt immediate payment:** `post_receipt` accepts optional `{amount, account_id}` and calls supplier payment creation inside the same transaction.
- **Financial summary in SQL:** aggregates over `orders` / `order_lines` (completed_at), `refunds` (recorded_at), `inventory_movements` (sale_consumption, return), `expenses` (expense_date). Boundaries converted from business-timezone dates to UTC half-open intervals (see `oms-reporting` skill).
- **Permissions:** accountant and owner get `expenses:manage`, `supplier_payments:manage`, `finance:view`, `cash:view`; manager gets `expenses:manage` and `cash:view`; owner only `cash:adjust`.

## Risks / Trade-offs

- [Backfill errors for earlier payments] → Migration backfill plus a reconciliation test: `sum(cash_movements where source in payments/refunds) == sum(active payments) - sum(refunds) - voids`.
- [Expense date vs payment date confusion] → Profit uses expense_date; cash uses paid_at; both shown in UI.
