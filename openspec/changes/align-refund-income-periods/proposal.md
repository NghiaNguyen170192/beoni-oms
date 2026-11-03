# Proposal

## Why

The financial summary attributes refunds to the period they are recorded, but the income listing currently attributes every refund to the period of the original sale. This makes the reports disagree when a refund is recorded after the sale period and fails the acceptance criterion that refunds are handled consistently.

## What Changes

- Make income listing refund amounts follow the refund's recorded period.
- Include earlier-period orders as refund rows when they have refunds recorded in the selected period; refund rows have zero sales amounts and reduce net sales by the tax-exclusive refund amount.
- Add a sale/refund row kind to the income API and CSV, and display refund rows distinctly in the income report.
- Verify that income listing net sales reconcile with the financial summary for sale day, refund day, and the combined period.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `financial-summary`: Specify period-scoped refund amounts and refund-only income rows so the income listing reconciles with the financial summary.

## Impact

- Backend accounting income-listing service and schema, reporting CSV export, generated OpenAPI client, and the profit report income table.
- Backend accounting/report tests and the income-report Playwright coverage.
- No database schema change or new dependency is expected.
