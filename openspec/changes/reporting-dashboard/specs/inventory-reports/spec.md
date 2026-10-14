# Spec Delta

## Purpose

Shows how stock moved over a period, separating recipe consumption from spoilage and manual corrections, and what the remaining stock is worth.

## ADDED Requirements

### Requirement: Stock movement summary
For each inventory item and period, the report SHALL show opening quantity, received, consumed by sales, adjustments by reason, returns, reversals, closing quantity, and estimated closing value, in the item's base unit.

#### Scenario: Coffee beans month
- **WHEN** a user runs the report for coffee beans this month
- **THEN** opening + received - consumed +/- adjustments + returns +/- reversals equals closing

### Requirement: Closing matches current balance
When the period ends today, the closing quantity SHALL equal the item's current balance.

#### Scenario: Current period
- **WHEN** the report period ends today
- **THEN** closing equals the inventory page quantity

### Requirement: Consumption separated from losses
The report SHALL distinguish recipe or direct-sale consumption from spoilage, expired, damaged, missing, physical count, and correction adjustments.

#### Scenario: Spoilage visible
- **WHEN** milk had 2 l consumed by sales and 0.5 l spoilage
- **THEN** the report shows them in separate columns

### Requirement: Stock status lists
The inventory report SHALL include current low-stock and negative-stock items and the total estimated inventory value.

#### Scenario: Inventory value
- **WHEN** a user views stock status
- **THEN** total value equals the sum of item quantity times average cost for non-negative items, and negative items are listed separately

### Requirement: Inventory report filters
Inventory reports SHALL filter by date range, item category, item type, and active status.

#### Scenario: Packaging only
- **WHEN** a user filters type packaging
- **THEN** only packaging items appear
