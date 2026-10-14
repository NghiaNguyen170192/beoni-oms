# Tasks

## 1. Report foundations

- [ ] 1.1 Create `modules/reporting/` with shared filter models, period presets, CSV streaming helper (UTF-8 BOM, ISO dates, plain numbers), and permission-specific schemas; verify unit tests for presets and CSV formatting
- [ ] 1.2 Add report indexes migration; verify round-trip

## 2. Dashboard

- [ ] 2.1 Implement dashboard query composing `financial_summary` and low-stock count, with role-based fields; verify service test that dashboard equals financial summary and API test that cashier responses omit cost/profit
- [ ] 2.2 Replace `routes/_layout/index.tsx` with the dashboard (metric cards, date range presets); verify build, lint, and a Playwright check of today's metrics after a seeded sale

## 3. Sales reports

- [ ] 3.1 Implement sales summary (grouping, payment breakdown, filters) and product performance queries with JSON and CSV routes; verify reconciliation tests (product sums == summary; cancelled excluded; renamed item single row)
- [ ] 3.2 Build Sales Reports page with filters, trend chart, tables, and export buttons; verify build and lint

## 4. Inventory reports

- [ ] 4.1 Implement movement summary (opening, received, consumed, adjustments by reason, returns, reversals, closing, value) and stock status queries with JSON and CSV routes; verify reconciliation test (opening + movements == closing == current balance)
- [ ] 4.2 Build Inventory Reports page; verify build and lint

## 5. Profit reports

- [ ] 5.1 Implement expense breakdown, profit statement, and period comparison with cost-limitation notice and CSV; verify service tests for spec examples and 403 for inventory staff
- [ ] 5.2 Build Profit Reports page with comparison view and estimate label; verify build and lint

## 6. Integration check

- [ ] 6.1 Add Playwright spec exporting each report and comparing CSV row counts and totals to on-screen values; verify spec passes
- [ ] 6.2 Seed about 50k orders and run `EXPLAIN ANALYZE` on dashboard and sales summary queries via the Postgres MCP; verify p95 under 2 s and record findings in design.md
