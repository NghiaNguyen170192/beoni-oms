# Proposal

## Why

Cashiers currently cannot add customer-specific charges such as shipping to a POS order, and completed bills do not preserve or display those charges. Owners also need a clear place under Admin to configure fee names and the shop name printed on receipts.

## What Changes

- Let owners configure named fee types and enable or disable them for POS use.
- Let owners configure the existing global VAT rate under Admin; use that rate for product prices and all POS fees.
- Let cashiers enter an optional amount for enabled fees while building an order. Fee amounts include VAT; extract the embedded VAT using the order's configured tax rate and include the entered amount in the backend-calculated amount due.
- Preserve fee names and amounts on each order as historical snapshots and show them in order details and printed receipts.
- Include VAT-inclusive fee charges separately in overall sales and financial summaries, including their embedded VAT in order tax, without attributing fees to product or category sales.
- Move the shop-name editor from Settings → Business to Admin while preserving its use on printed receipts and its owner/superuser authorization.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ordering`: Include configured, cashier-entered fees in open-order totals and preserve/display fee snapshots.
- `business-settings`: Make fee configuration, the existing global VAT rate, and the receipt shop name manageable under Admin by owners and superusers.
- `financial-summary`: Include fees in overall sales revenue as a distinct amount, separate from product sales.

## Impact

- Backend: order and fee configuration persistence, owner-only configuration APIs, order fee updates and authoritative totals, receipt/order schemas, payment balance compatibility, and financial summary calculations.
- Frontend: Admin fee, VAT-rate, and shop-name configuration; fee amount entry and totals in POS; order and receipt display.
- Database: migration for configured fee types and order fee snapshots, with integrity constraints.
- Generated OpenAPI client, backend tests, frontend build/lint, and Playwright coverage.
