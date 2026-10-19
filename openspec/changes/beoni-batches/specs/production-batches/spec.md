# Production Batches and Finished-Goods Inventory Specification

## Purpose

Separate batch production from POS sales and provide batch/lot traceability for produced menu items.

## Requirements

### Requirement: Inventory distinguishes raw materials from finished goods
The system MUST distinguish inventory used as production inputs from inventory held as sellable finished goods. Existing inventory records MUST remain valid after migration. The system MUST NOT determine stock behavior solely from whether a menu product has a recipe.

#### Scenario: Ingredient inventory is classified as raw material
- **WHEN** an authorized user views or edits an inventory item used as an ingredient
- **THEN** the item can be classified as a raw material
- **AND** it remains available to production formulas
- **AND** it is not decremented by POS sale completion

#### Scenario: Menu product is tracked as finished stock
- **WHEN** a menu product is configured for finished-goods tracking
- **THEN** it maps to a finished-good inventory item
- **AND** its sellable quantity is derived from posted finished-goods movements/lots

### Requirement: Production formulas define inputs and outputs
A production formula MUST define ingredient quantities per run and one or more finished-good menu-item mappings. It MAY provide typical output quantities, but each batch MUST be able to select its own output products and planned quantities independently. Formula versions MUST be immutable from the perspective of batches already created or completed against that version.

#### Scenario: Formula produces multiple menu items
- **WHEN** a formula defines multiple output products
- **THEN** one production batch can produce actual quantities for each output
- **AND** a batch may select a different subset or mix of those products without changing the formula's ingredient quantities
- **AND** each output quantity is received into a separate traceable lot linked to the same batch

#### Scenario: Reuse a formula for different production mixes
- **WHEN** a baker selects the same formula for separate batch runs
- **THEN** each batch independently records its selected output products and quantities
- **AND** the batch list can be filtered by the formula and produced menu items

#### Scenario: Formula is changed after a batch is created
- **WHEN** a new formula version is saved
- **THEN** existing batches retain their original formula snapshot and quantities

### Requirement: A batch records planned and actual production
The system MUST allow an authorized user to create a draft batch with planned output and ingredient quantities, record actual ingredient consumption and actual good/waste output quantities, and record when production finished. The system MUST distinguish `created_at` from the actual `finished_at` timestamp/date.

#### Scenario: Record a batch of five 35 ml flans
- **WHEN** a user completes a batch whose actual good output is five 35 ml flans
- **THEN** the batch records five as the actual finished quantity for that menu product
- **AND** records the actual raw-material quantities consumed
- **AND** records the actual finished date/time
- **AND** creates finished-goods stock linked to that batch
- **AND** records the total consumed-material cost for the batch without deriving a cost per flan

#### Scenario: Actual yield differs from planned yield
- **WHEN** actual output is lower or higher than planned output
- **THEN** the system records planned and actual quantities separately
- **AND** only actual good output is added to sellable inventory
- **AND** rejected or wasted output is recorded separately

### Requirement: Batch completion posts inventory atomically
Completing a batch MUST post raw-material consumption and finished-goods receipt in one database transaction. The batch MUST store total consumed-material cost and whether that total is uncertain; the system MUST NOT allocate batch cost to individual output items. If validation or any posting step fails, all stock, lot, cost, batch-state, and audit changes for that completion MUST roll back.

#### Scenario: Raw materials are insufficient
- **WHEN** the batch requires more raw material than is available and negative raw-material stock is not explicitly allowed
- **THEN** completion is rejected
- **AND** no ingredient movement, finished-goods receipt, lot, or completed status is persisted

#### Scenario: Batch completion is retried
- **WHEN** the same completion request is retried with the same idempotency key
- **THEN** the operation does not consume ingredients or create output stock a second time

### Requirement: Finished goods are lot-traceable
Every finished-goods quantity created by a completed batch MUST be associated with a batch/output lot containing the source batch, product, actual quantity, and finished timestamp. Per-item lot cost MUST remain unset/uncertain; the batch total cost is the cost record. Lot stock MUST be reconciled with the inventory ledger.

#### Scenario: View finished-goods inventory
- **WHEN** an authorized user views stock for a finished menu product
- **THEN** the system shows total available quantity
- **AND** supports inspecting quantities by source batch/lot and finished date

### Requirement: POS deducts finished goods, not raw materials
For menu products configured for finished-goods tracking, POS completion MUST deduct available finished-goods stock from one or more lots. POS completion MUST NOT deduct ingredients or invoke recipe-based raw-material consumption. If finished stock is insufficient, the sale MUST be rejected, even when global negative stock is enabled. Unmapped products MUST NOT create inventory movements or trigger recipe-based ingredient deduction.

#### Scenario: Sell one flan from a batch of five
- **GIVEN** a completed batch has added five sellable flans to finished-goods inventory
- **WHEN** the POS completes a sale of one flan
- **THEN** finished-goods stock decreases by one
- **AND** the source lot's remaining stock decreases by one
- **AND** raw-material balances remain unchanged by the sale
- **AND** the order line stores its lot allocation

#### Scenario: POS completion is retried
- **WHEN** order completion is retried with the same idempotency key
- **THEN** the system does not deduct finished stock or record COGS twice

#### Scenario: Finished-goods sale has no per-item cost
- **GIVEN** the source batch has a total material cost but no per-item output cost
- **WHEN** POS sells an allocated finished-good lot
- **THEN** the system leaves the order-line COGS unavailable/uncertain
- **AND** it does not invent or derive a per-item cost from the batch total

#### Scenario: Two sales compete for the last item
- **WHEN** concurrent order completions attempt to sell more units than are available
- **THEN** locking/transaction rules prevent overselling when stock enforcement is enabled
- **AND** a failed order completion leaves no partial stock or completion effects

### Requirement: Lot allocation is deterministic
When a sale is fulfilled from lot-tracked finished goods, the system MUST allocate stock by FEFO when expiry dates are present, otherwise by FIFO using finished timestamp. A single order line MAY be allocated from multiple lots. Allocation overrides MUST be permission-controlled and audited.

#### Scenario: Multiple lots are available
- **WHEN** a sale requires more units than remain in the first eligible lot
- **THEN** the system allocates from subsequent eligible lots in deterministic order
- **AND** records each allocation against the order line

### Requirement: Returns preserve source-batch traceability
A return MUST reference the original completed order line and its recorded lot allocation. Returned quantity MUST NOT exceed the quantity sold less previous returns. Sellable returned stock MUST be restored to the original lot; non-sellable returns MUST be recorded as waste or non-sellable stock and MUST NOT increase sellable quantity.

#### Scenario: Customer returns a sold flan
- **GIVEN** an order line records the batch/lot from which a flan was sold
- **WHEN** an authorized user accepts the flan as sellable and records a return
- **THEN** the return references the original order line and source batch/lot
- **AND** one unit is restored to that lot
- **AND** the return is visible in batch traceability

#### Scenario: Returned item is not sellable
- **WHEN** an authorized user marks a returned item as unsellable
- **THEN** the return is recorded with its disposition
- **AND** sellable finished-goods stock is not increased
- **AND** the original source batch remains traceable

### Requirement: Posted production history is auditable and correctable
Completed batches, posted movements, lot allocations, and returns MUST NOT be silently edited or deleted. Corrections MUST use explicit, permission-controlled reversal or adjustment operations with compensating ledger entries and audit records. A batch reversal MUST be rejected when downstream stock movements make a safe reversal impossible, unless a separately defined correction workflow safely handles those effects.

#### Scenario: User attempts to edit a completed batch
- **WHEN** a user attempts to change posted quantities on a completed batch
- **THEN** the system rejects direct mutation
- **AND** directs the user to an authorized correction/reversal workflow

### Requirement: Production permissions and audit are enforced
The system MUST enforce permissions for viewing batches, creating/editing drafts, completing batches, backdating finish dates, reversing batches, overriding lot allocation, and viewing traceability. Completion, backdating, reversal, correction, and allocation override MUST be auditable.

#### Scenario: User lacks completion permission
- **WHEN** a user without production-completion permission attempts to complete a batch
- **THEN** the request is rejected without posting inventory changes

### Requirement: Production data appears in inventory and reports
Finished-goods movements and batch outputs MUST be represented in inventory movement/stock-status reporting. The system SHOULD provide a production report showing batches, outputs, actual yield, waste, finished date, and product. Cost and sales reports MUST use consistent batch/lot cost snapshots and existing accounting conventions.

#### Scenario: Reconcile a batch and its sale
- **WHEN** a user reviews a completed batch, the related sale, and inventory reports
- **THEN** ingredient consumption, finished output, lot deductions, returns, waste, and remaining stock can be reconciled without double-counting

### Requirement: Batch material cost appears in accounting
The accounting summary MUST report total consumed-material cost from completed batches as production expense on each batch's `finished_at` date and subtract it from operating profit. The system MUST NOT allocate that total to individual output items; sales COGS for lots without a per-item cost MUST remain unavailable/uncertain.

#### Scenario: Include batch material cost in operating profit
- **GIVEN** a completed batch with a total material cost of 100,000 VND
- **WHEN** the accounting summary includes the batch's finished date
- **THEN** it reports the batch cost separately as production expense
- **AND** subtracts 100,000 VND from operating profit
- **AND** does not add the batch cost to per-item POS COGS
