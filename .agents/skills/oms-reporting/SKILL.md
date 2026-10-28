---
name: oms-reporting
description: Conventions for Beoni OMS reports, dashboard metrics, profit calculations, and CSV exports - inclusion rules, date/timezone boundaries, SQL aggregation, and reconciliation tests. Use when building or changing any report, dashboard number, or export.
---

# OMS Reporting

Reports live in `backend/app/modules/reporting/`. They are read-only and computed from source tables (orders, order lines, payments, refunds, inventory movements, expenses, supplier payments). Do not store pre-computed totals unless a measured performance need appears.

## Inclusion rules

- Completed sales = orders in `COMPLETED`, `PARTIALLY_REFUNDED`, `REFUNDED`. Exclude `DRAFT`, `CONFIRMED`, `CANCELLED`.
- Gross sales = sum of line `unit_price * quantity` snapshots; discounts and taxes come from line/order snapshots, never current product prices.
- Refunds reduce net sales in the period the refund was recorded, not the original sale period.
- Payments are cash flow, not revenue. Never add payments to sales.
- COGS = sum of `-quantity * unit_cost` on inventory movements with `source_type = 'sales_order'`, minus approved returns to stock.
- Gross profit = net sales - COGS. Operating profit = gross profit - recorded operating expenses (expense date in range, not reversed).
- Flag results that include negative-stock or missing-cost movements.

## Dates

- Filters are dates in the business timezone (settings, default `Asia/Ho_Chi_Minh`).
- Convert `[date_from 00:00 local, date_to + 1 day 00:00 local)` to UTC and filter with `>= start AND < end`. Never use `BETWEEN` on timestamps.
- Group by local day/week/month with `date_trunc('day', ts AT TIME ZONE :tz)`.
- Sales date = order completion time; refund date = refund time; expense date = expense date field.

## Implementation

- One query function per report returning typed rows (`SalesSummaryRow`), used by both the JSON endpoint and the CSV export, so exports always match the screen.
- Aggregate in SQL (`func.sum`, `group_by`) - no Python loops over all orders. Watch for N+1 queries.
- Return `Decimal` and serialize money as strings or integers of VND in the API.
- CSV: `StreamingResponse` with `text/csv; charset=utf-8-sig` (Excel-friendly Vietnamese), same filters, same permission check as the report.
- Permission: `reports:view` for sales; `reports:financial` for COGS/profit/expenses.

## Reconciliation tests

For each report, seed a known scenario and assert:

- Net sales equals sum of completed line totals minus discounts minus refunds.
- Payment-method breakdown sums to recorded payments minus refunds paid out.
- Inventory report: `opening + received - consumed +/- adjustments + returns == closing`, and closing equals current balance.
- Product performance totals equal the sales summary totals.
- CSV rows equal JSON rows for the same filters.

Use the Postgres MCP to spot-check numbers and run `EXPLAIN ANALYZE` on slow report queries against seeded data (target p95 < 2s for dashboard).
