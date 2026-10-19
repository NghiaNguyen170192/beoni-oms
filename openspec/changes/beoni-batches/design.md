# Design: Batch Production and Finished-Goods Inventory

## Existing implementation reuse decisions

- `InventoryItem` is the canonical stock-item definition. Its existing `item_type` remains the subtype (ingredient, merchandise, packaging, or consumable); add a separate `role` (`raw_material`, `finished_good`, or `general`) so stock behavior is explicit. Backfill existing ingredients, packaging, and consumables as raw materials, and merchandise as general; API requests omitting `role` keep compatibility by deriving it from the legacy subtype. `InventoryBalance` holds one aggregate balance per item, and `InventoryMovement` is the append-only stock ledger. All stock changes must continue through `inventory.service.post_movements`, which locks balances in sorted item-ID order, applies existing valuation rules, and enforces the configured negative-stock policy. Do not introduce a parallel stock ledger.
- `Recipe` is already immutable-by-version and `RecipeLine` represents its ingredient inputs. Reuse each recipe version as a reusable production template, with output lines mapping allowed menu items to finished-good inventory items. Keep output quantities as typical-yield guidance, not a fixed output mix. Enforce a stable menu-to-inventory mapping across recipe versions. Existing versions with no output lines remain valid as production templates; POS does not consume recipe ingredients for unmapped products. Batch snapshots preserve the selected formula version and its ingredient/output mappings.
- Any sellable menu item may anchor a production formula when it has explicit finished-good outputs, including a `direct_sale` item. POS deducts stock only for menu items explicitly mapped to finished-good inventory; unmapped products do not affect inventory. Non-stock menu items cannot be formula outputs.
- `MenuItem` has prepared, direct-sale, and non-stock product types but no finished-stock mapping. Do not use product type or recipe existence as a proxy for finished-stock tracking. Add an explicit mapping/classification to inventory items, with a migration that leaves existing sales behavior intact until an audited opening balance is recorded.
- `ordering.service.complete_order` owns the parent order lock and uses `idempotency.execute` to make payment checks, completion steps, response storage, and commit atomic. Its current completion steps include `recipes.service.consume_stock`, which deducts recipe ingredients at POS. Replace that step with finished-lot deduction for explicitly mapped menu products; unmapped products must not cause inventory movements. Keep the order completion idempotency boundary and mark unavailable item-level COGS as uncertain.
- `MovementAllocation` allocates ingredient-ledger movements to order lines for COGS; it is not a finished-lot allocation. Add separate lot allocation records rather than changing its meaning. The inventory ledger remains the source for aggregate on-hand and valuation, while lot balances/allocation rows provide traceability and must reconcile to those movements.
- Stock returns are implemented in `recipes.service` as `StockReturn`/`StockReturnLine` and currently restore direct-sale linked stock; prepared-product returns are rejected. Payment refunds use separate `Refund`/`RefundLine` records and do not change stock. Extend the stock-return workflow for lot-tracked products without conflating it with payment refunds, and retain source-lot lineage for sellable returns.
- Reuse `audit.service.record`, the existing permission enum/role checks, and `idempotency.service` for new production actions. Register new SQLModel tables through `backend/app/models.py`; migrations belong in Alembic. Keep service functions as transaction owners and use the existing PostgreSQL-backed service/API and concurrency test conventions.

## Domain model

### Inventory item classification

Reuse the existing inventory item model where practical. Introduce or formalize an item role/type:

- `RAW_MATERIAL`: ingredients and consumables consumed by production.
- `FINISHED_GOOD`: a sellable menu item held as finished stock.
- `GENERAL`: other inventory items supported by the existing application, if needed for backward compatibility.

Do not infer raw-material/finished-good behavior from a menu item's recipe alone. Persist the classification and validate it at API boundaries. A menu product that is tracked as finished stock must resolve to a `FINISHED_GOOD` inventory item (or an explicit existing mapping between menu product and inventory item).

### Production formula / recipe

A versioned formula has:

- stable formula identity and version;
- name and active state;
- ingredient lines: raw-material inventory item, quantity per formula run/yield, and unit;
- output lines: finished-good inventory item, menu item, and planned quantity produced per formula run;
- optional notes and effective timestamp.

Formula versions used by posted batches are snapshots and must not change when a later formula version is edited. Use the existing recipe-version model if it can represent multiple output lines; otherwise extend it compatibly. Avoid duplicating the current recipe concept under a second name. Legacy recipe versions may omit outputs; they are not eligible for batch production until a version with explicit finished-good outputs is created.

When a draft selects a formula version, a positive `formula_runs` multiplier scales only the formula's ingredient quantities. The baker independently selects one or more allowed output products and their planned quantities for that batch; do not scale outputs to a fixed formula ratio. Copy the selected output mappings and planned quantities into the batch so later formula versions cannot rewrite them.

### Production batch

A batch records:

- unique human-readable batch number;
- formula identity and exact formula version/snapshot, when formula-driven;
- status: `DRAFT`, `IN_PROGRESS` (optional if the current workflow needs it), `COMPLETED`, `CANCELLED`, `REVERSED`;
- planned production date and planned output quantities;
- selected formula runs/multiplier when the batch uses a reusable formula;
- actual production start timestamp (optional) and `finished_at` timestamp/date;
- creator, completer, notes, and audit timestamps;
- actual ingredient consumption lines;
- actual output lines, including finished-good item, planned quantity, actual good quantity, rejected/wasted quantity, and unit;
- total consumed-material cost and an uncertainty flag, stored once at batch level;
- references to posted inventory movements and output lot records.

If the user records a completed batch after the real-world production date, `finished_at` must represent the actual production completion time/date and `created_at` must preserve when it was entered. Backdating is permission-controlled and audited.

### Finished-goods lot

Each output line with positive good quantity posted by a completed batch creates a traceable lot (or lot balance record) with:

- lot ID and displayable lot/batch number;
- source batch and source output line;
- finished-good inventory item;
- produced quantity, current on-hand quantity, and reserved quantity if reservations exist;
- finished timestamp and optional expiry/best-before date;
- no allocated per-item unit cost; item-level cost remains unset/uncertain;
- references to the batch output and the append-only inventory movements contributing to its lot balance.

The stored lot on-hand quantity is updated in the same transaction as each movement. Signed lot-movement rows tie that balance back to the aggregate inventory ledger, and separate order-line allocation rows explain which lots fulfilled each sale.

A batch that produces two menu products creates a separate lot/output balance for each product, both linked to the same batch.

### Sales allocation and returns

On POS completion, allocate each finished-good order line to one or more available lots. Persist the allocations against the order line and the corresponding inventory movement. A line can be fulfilled by multiple lots if necessary. Default allocation is FEFO where expiry is present; otherwise FIFO by `finished_at`, with deterministic tie-breaking by lot ID.

A return must reference the original completed order line and its original lot allocation. Returnable quantity cannot exceed the quantity sold minus quantities already returned. Returned stock is assigned back to the originating lot only if the return is accepted as sellable; otherwise record it as waste/non-sellable stock through a separate movement/status. Never create a returnable lot without a traceable origin when the sold item was lot-tracked.

## Inventory ledger rules

- Batch completion posts negative movements for consumed raw materials and positive movements for actual good output quantities.
- Sum the consumed-material movement values into a batch-level total cost, preserving a cost-uncertain flag if any consumed movement has uncertain cost. Do not allocate this cost to output items or lots.
- Report total batch production cost as an expense on `finished_at` in the accounting summary and subtract it from operating profit; do not create general-ledger postings in this change.
- Rejected/wasted output is recorded separately and is not added to sellable stock.
- POS completion posts negative movements against finished-goods lots only.
- POS must not post ingredient/raw-material movements.
- Accepted returns post positive movements against the original lot, or an explicit non-sellable/waste location/status if rejected.
- Manual adjustments and batch/sale reversals use compensating movements; never delete or rewrite posted movements.
- All quantities use `Decimal` and the existing `Numeric(18,4)` conventions. Money/cost uses `Decimal` and `Numeric(18,2)` unless existing cost precision requires a compatible higher-precision column.

## Transaction and idempotency boundaries

### Complete batch

Within one database transaction:

1. Lock the batch and all affected inventory balances in deterministic item-ID order.
2. Validate state, formula snapshot, quantities, units, and required permissions.
3. Validate sufficient raw-material stock under the configured negative-stock policy; default to rejecting shortages.
4. Post ingredient consumption movements.
5. Post finished-goods receipt movements and create lot balances.
6. Store final actual quantities, finished timestamp, total material cost, cost uncertainty, and audit event.
7. Mark the batch completed.

Any failure rolls back all effects. Require an `Idempotency-Key` for completion and reversal endpoints, following the existing idempotency service.

### Complete POS sale

Within the existing order-completion transaction:

1. Lock the order and relevant finished-good balances/lots.
2. Validate payment and order state using existing ordering/payment rules.
3. Allocate lot quantities and validate available finished-good stock.
4. Post finished-good lot deductions and persist allocations.
5. Complete the order and store COGS as unavailable/uncertain for finished-good lots without a per-item cost.

No ingredient consumption occurs in this path. Retry with the same idempotency key must not deduct stock twice.

The accounting financial summary reports `production_cost` separately from sale COGS and includes it as an expense when calculating operating profit. Output-lot sales without per-item cost remain visible in the existing uncertain/missing COGS metrics.

### Reverse batch

A completed batch cannot be edited or cancelled as if it had never happened. Reversal is allowed only if the batch's produced stock has not been consumed, returned, adjusted, or otherwise moved in a way that prevents a safe reversal. If some output remains, the implementation may either reject full reversal and require an explicit correction workflow, or support a controlled partial correction in a separate operation. Do not silently create negative stock or erase traceability.

## API and UI

Add a production module under `backend/app/modules/production/` consistent with existing domain modules. Reuse inventory, recipe, ordering, audit, and idempotency services instead of duplicating ledger logic.

Suggested API surface (adapt names to current conventions):

- `GET/POST /production/batches`
- `GET/PATCH /production/batches/{id}` for draft-only edits
- `POST /production/batches/{id}/start` if `IN_PROGRESS` is used
- `POST /production/batches/{id}/complete` with `Idempotency-Key`
- `POST /production/batches/{id}/reverse` with `Idempotency-Key` and reason
- `GET /production/batches/{id}/traceability`
- `GET/POST /production/formulas` and versioned formula endpoints, or reuse existing recipe endpoints where practical
- `GET /inventory/items/{id}/lots` or an equivalent finished-goods lot query

React pages should include:

- Production batches list with status, batch number, formula, planned/actual quantities, production date, finished date, creator, and filters.
- Create/edit draft batch screen with formula selection, planned outputs, actual ingredient consumption, actual outputs, waste/rejects, notes, and finish date.
- Batch detail page showing ingredient movements, output lots, cost, and downstream sales/returns.
- Finished-goods inventory view that displays on-hand quantities and lot/batch/finished-date details.
- POS stock availability and shortage feedback for finished goods; no ingredient stock deduction in POS.
- Order/return detail showing lot and source batch where applicable.

## Permissions and audit

Reuse the existing role/permission dependency patterns. Add explicit permissions for viewing production, creating/editing drafts, completing batches, backdating completion, reversing batches, and viewing traceability. Only authorized users can complete or reverse a batch. Every completion, backdate, reversal, manual correction, lot allocation override, and return disposition must record actor, timestamp, reason where applicable, and relevant before/after values.

## Migration and compatibility

- Add Alembic migrations; do not modify production schema outside migrations.
- Preserve existing raw-material inventory and recipe history.
- POS completion must not deduct recipe ingredients for existing or new menu/recipe records.
- Define a migration/backfill strategy for existing sellable menu items: either create finished-good inventory mappings with zero opening stock and require an initial stock count, or provide an explicit audited opening-stock import. Do not invent historical batches for stock that cannot be traced. The rollout path is to create a finished-good inventory item at zero, add a versioned recipe output mapping, then post a physical-count adjustment from zero; that adjustment creates an audited opening-stock lot linked to its stock-adjustment line, not a fabricated production batch. Existing nonzero balances are not retroactively assigned to a lot.
- Feature-gate finished-stock enforcement if necessary during migration, but POS must never deduct ingredients. Tracked finished goods are deducted from lots; unmapped products do not affect inventory.
- Existing orders and movements remain readable; new traceability guarantees apply to new batch-produced stock unless an explicit historical mapping is provided.

## Testing strategy

Use PostgreSQL-backed integration tests for locking, constraints, rollback, and idempotency. Unit tests alone are insufficient for transaction semantics. Add API tests for permissions and React/Playwright tests for the complete production-to-sale-to-return workflow. Keep all existing project test conventions and regenerate the OpenAPI client after API changes.
