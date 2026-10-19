# Proposal: Batch Production and Finished-Goods Inventory

## Why

Beoni OMS currently treats menu recipes, raw-material inventory, and POS completion as tightly coupled concepts. This makes the POS behave as if every sale is a production event: ingredient stock can be consumed at checkout, even when the product was prepared earlier in a kitchen. It also makes it difficult to answer which production batch a sold or returned item came from.

Introduce a batch-production workflow that separates production from sales. A production batch consumes ingredients according to a versioned production formula, records the actual finished quantities produced, and creates traceable finished-goods stock lots. POS checkout then sells from finished-goods stock and does not consume recipe ingredients.

## Scope

- Support inventory items used as raw materials and sellable finished/menu goods.
- Support reusable production formulas (recipes) that define ingredient quantities per run and the menu products a run may produce. Each batch record can choose its own planned and actual output mix.
- Create and finish production batches with planned and actual output quantities, ingredient consumption, production date/time, and finished date/time.
- Post raw-material consumption and finished-goods receipt atomically when a batch is completed.
- Track finished-goods quantities by production batch/lot and preserve lot allocation on order lines for traceability and returns.
- Change POS inventory behavior so a sale deducts finished-goods inventory only; it never deducts recipe ingredients.
- Support stock adjustments, waste/spoilage, sales, and returns without rewriting posted history.
- Add UI, API, permissions, audit events, migrations, automated tests, and reporting needed for this workflow.
- Record consumed-material cost as a batch total, without calculating per-item output cost, and include production cost in the accounting report.

## Out of scope

- Full manufacturing resource planning, work centers, labor scheduling, or capacity planning.
- Serial-number tracking for every individual piece. Batch/lot-level traceability is the initial requirement.
- Automatic production scheduling or demand forecasting.
- Multi-warehouse transfers unless the existing inventory module already supports locations and the implementation can reuse them without expanding this change.
- Full accounting/general-ledger redesign.

## Product decisions

1. A recipe is a production formula, not an instruction to deduct raw materials at POS checkout.
2. A production batch may produce one or multiple menu products and may produce actual quantities different from planned quantities.
3. Completing a batch is the posting boundary: ingredient consumption and finished-goods receipt must commit together or not at all.
4. POS completion deducts finished-goods quantities from traceable lots; it does not consume raw materials.
5. The default lot allocation policy is FEFO (earliest expiry first) when expiry dates exist, otherwise FIFO by finished timestamp. Users with permission may select a lot only where business rules allow it.
6. Finished goods without enough available stock cannot be sold when stock enforcement is enabled. Do not silently fall back to consuming ingredients or creating negative finished stock.
7. Posted batch, sale, and return records are immutable. Corrections use explicit reversal/adjustment operations with audit history.
8. A formula is a reusable batch template. Each production run is a separate batch record; output product mix and quantities are selected per run.
9. Production cost is the total cost of consumed materials for a batch. Do not allocate it to output items; report it as an expense on the batch's finished date, and leave item-level sales COGS uncertain.

## Expected outcome

A staff member can record a batch of five 35 ml flans, consume the required amount of milk, eggs, sugar, and packaging, receive five flans into finished-goods inventory, sell one flan without changing ingredient balances, and trace that sold flan back to the batch if it is returned.
