# Design

## Context

See proposal.md and the `financial-summary` delta. `income_listing` currently selects orders by completion period, then attaches all their refunds. The same row shape is used by the finance API and the income CSV; the React profit report renders those rows from the generated client.

## Goals / Non-Goals

**Goals:**
- Keep the refund-recorded-date rule used by `financial_summary`.
- Make income rows and their net sales totals use the same period boundaries as the summary.
- Clearly distinguish sales from refund activity in the API, CSV, and income table.

**Non-Goals:**
- Change how payments, order statuses, or summary formulas are calculated.
- Add refund-level pagination or change the refund workflow.

## Decisions

- Keep one sale row per order completed in the selected period. Include only that period's refunds in its refund and net-sales amounts; retain payment status based on all refunds against the order.
- Aggregate refunds recorded in the selected period by earlier order into one refund row per order. Use `kind` (`sale` or `refund`) to distinguish row types. A refund row carries the gross refund total, zero sales, discounts, fees, and tax, and negative net sales equal to the refund excluding embedded tax.
- Add `kind` to the income response and CSV, regenerate the OpenAPI client, and label refund rows in the existing income table. Use row kind with order ID as the table key because a selected period cannot produce both a sale row and an earlier-sale refund row for the same order.
- Test one order completed on day 1 and refunded on day 2, at a nonzero tax rate, comparing listing net sales with the summary on each day and across both days.
- Keep the existing backend service as the source of period bounds and refund tax calculation; no database or migration change is needed.

## Risks / Trade-offs

- A refund row refers to an order completed before the selected period → Preserve the order completion date and show the row kind so users can distinguish historical order details from current-period activity.
- The income API and CSV gain a row kind → Regenerate the client and update the UI and CSV assertions in the same change.
