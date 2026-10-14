# Design

## Context

Depends on `inventory-core` (`post_movements`, balances, conversion helper) and `platform-foundation` (idempotency, audit). Supplier payments arrive in `accounting-basic`.

## Goals / Non-Goals

**Goals:** a receipt workflow that is the single source of incoming stock and supplier payables.

**Non-Goals:** purchase orders before receipt, partial receiving against POs, supplier returns as a separate document (use reversal or a negative adjustment), multi-currency purchases, VAT input accounting.

## Decisions

- **Tables:** `suppliers`, `stock_receipts` (reference unique, status check, total, posted_at, posted_by, reversed_by_id, reversal_of_id, reversal_reason), `stock_receipt_lines` (purchase_qty, purchase_unit_cost, base_qty, base_unit_cost, line_total), `supplier_payables` (receipt_id unique, supplier_id, amount, paid_amount, status).
- **Payable as its own row** rather than columns on the receipt so `accounting-basic` can allocate payments to payables without touching receipts. Amount reversal sets payable amount to 0 and status `cancelled`.
- **Base cost precision:** `base_unit_cost = purchase_unit_cost / factor` stored at Numeric(18,4); `line_total` is computed from purchase values to avoid rounding drift; movement value = line_total.
- **Reversal as a new receipt row** with negative lines (`reversal_of_id` set) so lists and reports see both documents; original gets `status = reversed`.
- **Reference generation:** client may supply a reference; otherwise the backend generates `PN-YYYYMMDD-####` per business-timezone day.
- **Locking:** post locks the receipt row first, then balances via `post_movements`.

## Risks / Trade-offs

- [Reversing after stock was consumed changes average cost unexpectedly] → Reversal uses original cost; average recomputed; if quantity would hit <= 0 the reversal requires negative stock allowed, else rejected with a clear message.
