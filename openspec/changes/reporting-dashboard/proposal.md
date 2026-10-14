# Proposal

## Why

The fifth question in goals.md, "How is my business performing?", needs trustworthy reports (section 8). All source data now exists; this change presents it consistently and makes it exportable, reconciling with source transactions.

## What Changes

- Dashboard for a date range (default today): net sales, completed order count, average order value, discounts, refunds, COGS, gross profit, expenses, operating profit, low-stock count.
- Sales summary: gross, discounts, refunds, net, order count, average order value, grouped by day, week, or month, payment-method breakdown; filters by date, cashier, payment method, category, order status.
- Product performance: quantity, gross, discounts, net, estimated cost, gross profit, share of net sales, best and least sellers.
- Inventory and consumption: opening, received, consumed by sales, adjustments (by reason), returns, closing, estimated value; recipe consumption separated from spoilage and manual adjustments.
- Expense and profit report with comparison between two periods.
- CSV export for each report respecting filters and permissions.
- Reports section in the React app with charts for trends.

## Capabilities

### New Capabilities

- `dashboard`: at-a-glance business metrics for a period.
- `sales-reports`: sales summary and product performance.
- `inventory-reports`: stock movement and consumption reporting.
- `profit-reports`: expense breakdown and profit with period comparison.
- `report-export`: CSV exports matching on-screen reports.

### Modified Capabilities

None.

## Impact

- Backend: new `backend/app/modules/reporting/` (read-only queries, CSV streaming), indexes on `orders.completed_at`, `refunds.recorded_at`, `inventory_movements(item_id, created_at)`, `expenses.expense_date`; permissions `reports:sales`, `reports:inventory`, `reports:financial`.
- Frontend: replace the template dashboard (`routes/_layout/index.tsx`), add `routes/_layout/reports/*`; adds a lightweight chart dependency (recharts, used by shadcn charts).
- Reuses `financial_summary` from `accounting-basic`.
