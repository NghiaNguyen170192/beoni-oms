# Design

## Context

`ordering.complete_order` runs steps in one transaction (validate → `payments.ensure_paid`). This change adds `stock.consume` as the final step before status change. `inventory.post_movements` already does sorted locking, weighted-average costing, negative-stock policy, and `cost_uncertain` flags.

## Goals / Non-Goals

**Goals:** correct, aggregated, single-shot deduction with per-line COGS; no oversell under concurrency.

**Non-Goals:** modifiers that change recipes per order (e.g. "less sugar"), sub-recipes/batch production (e.g. pre-made syrup), yield/waste factors, recipe import.

## Decisions

- **Unified versioned consumption definition.** `recipes` (menu_item_id, version, effective_from, kind `recipe|stock_link`) + `recipe_lines` (inventory_item_id, quantity). A direct-sale link is a one-line version of kind `stock_link`, so lookup, versioning, audit, and cost preview share one code path. Applicable version = max effective_from <= completion time. Alternative: separate link table - rejected as duplicate logic.
- **Calculation is a pure function** `aggregate_requirements(lines, versions) -> dict[item_id, Decimal]` plus per-line breakdown, unit tested without DB.
- **Concurrency:** order row locked first (from ordering), then balance rows sorted by item id inside `post_movements`; availability checked after locks are held, which makes oversell impossible. Idempotency: completion key plus status check under lock.
- **Line COGS allocation:** movements are posted per aggregated item, but each line's COGS = sum(line quantity x recipe quantity x average cost at lock time), computed from the same locked average costs, so `sum(line COGS) == sum(movement values)`. Movements store `source_type=order`, `source_id`, and the movement-to-line breakdown in a `movement_allocations` table for traceability.
- **Shortage error** returns 409 with structured `shortages: [{item, required, available, unit}]` for POS display.
- **Returns:** `stock_returns` and lines referencing order lines; quantity cap enforced under order lock; cost = line's original per-unit COGS; separate idempotency scope.

## Risks / Trade-offs

- [Completion latency grows with recipe size] → One query loads all applicable versions for the order's items; one locked query for balances. Target p95 < 1 s.
- [Orders paid but blocked by shortage] → POS shows shortages and lets a manager either receive/adjust stock or refund; documented in UI copy.

## Migration Plan

Additive tables and nullable columns on `order_lines`; orders completed before this change have null COGS and are flagged "no cost data" in reports.
