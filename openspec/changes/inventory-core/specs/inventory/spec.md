# Spec Delta

## Purpose

Tracks what stock the business holds: inventory items, their units, current balances and weighted-average value, and an auditable ledger of every stock movement.

## ADDED Requirements

### Requirement: Inventory item attributes
An inventory item SHALL have a unique SKU, name, optional description, category, type (ingredient, merchandise, packaging, consumable), base unit, purchase unit, conversion factor, minimum stock threshold, active flag, optional unique barcode, and creation and modification timestamps.

#### Scenario: Create coffee beans
- **WHEN** an inventory manager creates "Coffee beans" with base unit g, purchase unit kg, conversion factor 1000
- **THEN** the item is saved with zero quantity and zero average cost

#### Scenario: Duplicate SKU
- **WHEN** a user creates an item with an existing SKU
- **THEN** the system rejects it with a conflict error

### Requirement: Valid unit conversion
The conversion factor SHALL be a positive number expressing base units per purchase unit; zero, negative, or missing factors SHALL be rejected. When purchase and base units are equal the factor SHALL be 1.

#### Scenario: Zero factor rejected
- **WHEN** a user saves an item with conversion factor 0
- **THEN** the system rejects it with a validation error

#### Scenario: Purchase quantity converted
- **WHEN** 5 kg of coffee beans are converted with factor 1000
- **THEN** the base quantity is 5000 g

### Requirement: Stock changes only through movements
Item quantity and value SHALL change only by posting inventory movements; item edit operations SHALL NOT change quantity or cost.

#### Scenario: Edit cannot change quantity
- **WHEN** a user edits an item and submits a different quantity
- **THEN** the quantity is unchanged

### Requirement: Movement records are complete and immutable
Each movement SHALL record item, signed quantity in base units, unit cost, movement type (receipt, sale_consumption, adjustment, return, reversal), source document type and id, actor, and timestamp. Movements SHALL NOT be edited or deleted.

#### Scenario: Movement references its source
- **WHEN** any document posts a movement
- **THEN** the movement identifies that document by type and id

### Requirement: Balance equals movement history
For every item, the current quantity SHALL equal the sum of its movement quantities, and concurrent postings SHALL NOT overwrite each other.

#### Scenario: Concurrent postings
- **WHEN** two movements of -10 and -20 are posted concurrently on an item with quantity 100
- **THEN** the resulting quantity is 70 and equals the movement sum

### Requirement: Weighted-average valuation
Incoming movements with a cost SHALL update the item's average unit cost as total value divided by total quantity; outgoing movements SHALL be valued at the current average cost and record that cost.

#### Scenario: Receive at a different cost
- **WHEN** an item with 1000 g at 0.5 VND/g receives 1000 g at 0.7 VND/g
- **THEN** quantity is 2000 g and average cost is 0.6 VND/g

#### Scenario: Missing cost flagged
- **WHEN** stock is consumed from an item whose average cost is unknown or whose quantity is negative
- **THEN** the movement is flagged as having uncertain cost

### Requirement: Low and negative stock visibility
Users with inventory view permission SHALL list items at or below their minimum threshold and items with negative quantity.

#### Scenario: Low-stock list
- **WHEN** milk has quantity 500 ml and minimum 1000 ml
- **THEN** milk appears in the low-stock list

### Requirement: Movement history per item
Users with inventory view permission SHALL view an item's movements filtered by date range and movement type, with running balance, newest first and paginated.

#### Scenario: Filter by type
- **WHEN** a user filters coffee beans history by adjustment
- **THEN** only adjustment movements are shown

### Requirement: Deactivate instead of delete
Items with any movement SHALL NOT be deleted; they MAY be deactivated, which hides them from selection for new documents.

#### Scenario: Delete item with history
- **WHEN** a user deletes an item that has movements
- **THEN** the system rejects the deletion
