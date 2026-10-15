# Design

## Context

Builds on `platform-foundation` (permissions, audit, idempotency, settings with `allow_negative_stock`). This module becomes the only writer of stock for the rest of the system.

## Goals / Non-Goals

**Goals:** one posting API (`inventory.service.post_movements`) used by adjustments, receipts, sales, returns, and reversals; concurrency-safe balances.

**Non-Goals:** multiple warehouses/locations, batch/lot or expiry tracking, FIFO costing, barcode scanning hardware.

## Decisions

- **Tables:** `inventory_items` (definition), `inventory_balances` (item_id PK, quantity Numeric(18,4), avg_unit_cost Numeric(18,4), value Numeric(18,2), updated_at), `inventory_movements` (append-only), `stock_adjustments` + `stock_adjustment_lines`.
  Separate balance table keeps item edits from contending with stock locks. Alternative: compute balances from movements on read - rejected for POS latency.
- **Posting function** `post_movements(session, lines, source_type, source_id, actor)`:
  1. lock balance rows `SELECT ... FOR UPDATE` sorted by item_id;
  2. compute cost per line (incoming: given cost; outgoing: current average);
  3. insert movements and update balances in the same transaction; never commits.
  Callers own the commit (see `oms-transactional-workflow`).
- **Average cost rule:** when quantity before receipt is <= 0, new average = incoming cost (do not average with a negative balance). Movements posted while quantity is negative or average is zero set `cost_uncertain = true`.
- **Unit cost precision** Numeric(18,4) because per-gram costs are fractional VND; monetary totals rounded to Numeric(18,2) (VND has no minor unit in practice, but 2 decimals keeps calculations safe).
- **Units** are free-text codes from a fixed list (g, kg, ml, l, piece, pack, bottle, cup, box); conversion is a factor on the item, not a global unit table.
- **Permissions:** `inventory:view` (owner, manager, inventory_staff, accountant), `inventory:manage` (owner, manager, inventory_staff), `inventory:adjust` (owner, manager, inventory_staff), `inventory:reverse` (owner, manager).
- **Seed data:** inventory categories "Nguyên vật liệu" (ingredients), "Công cụ dụng cụ" (tools and packaging), "Món bán" / "Hàng bán sẵn" (merchandise), "Bao bì" (packaging), carried over from the prototype's `management_group` values.
- **SKUs** come from PostgreSQL sequence `inventory_item_sku_seq`, formatted `SP-{n:05d}` in the service at create time; the SKU is absent from create/update payloads. Gaps from rolled-back inserts are accepted.
- **Starter catalog:** the codes migration seeds ten bakery ingredients in "Nguyên vật liệu" with zero balances: Trứng gà (piece; box of 30), Bột mì (g; kg), Bột nở (g; kg), Siro (ml; bottle of 700), Sữa tươi (ml; l), Đường (g; kg), Kem tươi whipping (ml; l), Muối (g; kg), Tinh chất vani (ml; bottle of 100), Rượu rum (ml; bottle of 700). Downgrade removes only seeded items without movements.
- **UI labels from the prototype** are the Vietnamese translations: "Kho hàng" (page title), "Mã hàng" / "Tên hàng" (SKU / name columns), "Theo mã hoặc tên hàng" (search placeholder), "Đang kinh doanh" / "Ngừng kinh doanh" (active / inactive), "Dưới định mức tối thiểu" (below minimum). English equivalents are used when the business language is English. The prototype's "Vượt định mức tối đa" (above maximum) filter is out of scope because goals.md defines no maximum threshold.

## Risks / Trade-offs

- [Hot rows for popular ingredients under concurrent sales] → Short transactions and sorted locking; acceptable for single-shop load.
- [Balance drift if someone writes SQL directly] → Reconciliation check (`balance == sum(movements)`) in tests and in `hardening-deployment` as an admin check.

## Migration Plan

New tables only; downgrade drops them.
