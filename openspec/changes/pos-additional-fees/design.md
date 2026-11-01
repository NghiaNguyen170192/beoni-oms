# Design

## Context

Orders currently persist product lines and calculate `total` as product subtotal minus discounts. Payment balance and completion checks already use `order.total`; receipts print product lines and that total. The singleton business settings row stores the shop name, and the financial summary recognizes product sales from completed orders. See `proposal.md` and the deltas in `specs/`.

## Goals / Non-Goals

**Goals:**
- Keep fee configuration, order fee snapshots, and recalculated totals transactionally consistent.
- Preserve completed-order fee labels and values when owners later edit or disable a fee type.
- Keep fee charges out of product discounts, product/category sales, and stock cost while including their embedded VAT in order tax.
- Place fee and receipt shop-name controls in the owner-only Admin area.

**Non-Goals:**
- Percentage-based fees, automatic fee calculation, per-fee tax rates, or currency conversion.
- A complete tax classification engine for all Vietnam VAT cases; fees use the application's existing configured order tax rate.
- Assigning fees to product lines or inventory costs.
- Changing the existing general business settings or payment/refund workflows beyond the order total they already consume.

## Decisions

1. **Store fee types separately from applied order fees.** Add a fee-type record with a name, active flag, and timestamps, and an order-fee record with order reference, fee-type reference, fee-name snapshot, and VND amount. A unique order/fee-type constraint prevents duplicate rows. Fee types are disabled rather than deleted, preserving foreign-key history; order snapshots retain the sold name even after a rename.

2. **Keep fee values on the order, not in client-only cart state.** Add an order fee total and update fee rows through the existing open-order workflow under the order row lock. Validate fee type and amount on the backend, omit zero amounts, and derive the order total from product subtotal minus discounts plus fee total. Fee amounts entered at POS include VAT; extract the embedded VAT using the order's saved tax-rate snapshot and add it to order tax without changing the amount due. Existing payment and completion logic already bases balances on `order.total`, so it will include fees without a separate payment path.

3. **Use owner settings permission for configuration.** Fee-type management, VAT-rate configuration, and shop-name updates use the existing settings-management authorization, which maps superusers to owner. Reuse the existing global `business_settings.tax_rate` and its audit path; expose it under Admin and remove its editor from Settings → Business. The configured rate applies to tax-inclusive product prices and POS fees, and each order retains its rate snapshot. Audit fee configuration and shop-name changes. Expose active fee types for POS entry; owner administration can also list disabled types.

4. **Move only the shop-name and VAT-rate controls, not the entire business settings form.** Add focused owner-only Admin controls for the shop name, VAT rate, and fee types, and remove the shop-name and VAT-rate inputs from Settings → Business. Use dedicated update requests where needed so saving an Admin control does not resubmit unrelated settings fields. Continue using the same stored business name as the receipt heading.

5. **Keep fee charges distinct in accounting summaries.** Include gross VAT-inclusive fee charges separately in financial summary totals and order income rows; retain the existing net-sales formula, subtracting discounts, refunds, and total taxes, including VAT extracted from fees. Leave product-line, product/category, and stock-cost reporting unchanged. Fees do not create inventory or cash-movement records; actual customer money remains recorded through existing payment flows.

6. **Keep disabled fees stable on existing orders.** Disabling a fee prevents it from being newly applied on the POS, but does not delete or rewrite applied fee snapshots. An existing order can retain its applied fee through completion; a cashier may remove a disabled fee while the order remains open, but cannot add or increase it after it has been disabled.

## Risks / Trade-offs

- [Fee total participates in payment sufficiency and refunds through the existing order total] → Cover payment, pay-and-complete, and refund boundaries with backend tests; keep the fee line visible on receipts and order details.
- [A fee type can be renamed while an order is open] → Persist the fee name snapshot with the order row and never derive historical display names from current configuration.
- [The application has one configured VAT rate rather than per-item or per-fee rates] → Use the Admin-configured rate for products and fees, snapshot it on each order, and do not claim this implements every possible statutory VAT classification.
- [Refunds are order-level and are not attributed to specific fee rows] → Report collected fees separately and retain the existing aggregate refund treatment; do not claim fee-specific net revenue.
- [Existing Settings API currently updates several settings together] → Provide a dedicated audited shop-name update operation and retain the current endpoint for remaining business settings.

## Migration Plan

1. Add fee-type and order-fee tables, the order fee-total column with a zero default, and a revised order-total integrity check. Existing orders migrate with no fees and unchanged totals.
2. Deploy backend APIs and regenerated client, then the Admin/POS/receipt UI. Fee types are opt-in and existing order behavior is unchanged until an owner enables a type.
3. On rollback, roll back application code before schema removal. Preserve fee data unless an explicit data-retention decision authorizes dropping it.
