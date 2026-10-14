# Spec Delta

## Purpose

Deducts inventory and captures cost of goods sold automatically when a sale is completed, enforces the stock availability policy, and handles returns to stock explicitly.

## ADDED Requirements

### Requirement: Consumption calculated per completed order
On completion, the system SHALL compute required stock per inventory item as the sum over lines of quantity times the applicable recipe or stock-link quantity, aggregated across all lines before any stock update. Non-stock items SHALL NOT consume stock.

#### Scenario: Two drinks share an ingredient
- **WHEN** an order with 2 iced milk coffees (18 g beans each) and 1 hot coffee (20 g beans) is completed
- **THEN** a single requirement of 56 g coffee beans is computed and deducted

### Requirement: Prepared and direct-sale items must have consumption defined
Completing an order containing a prepared item without an applicable recipe, or a direct_sale item without a stock link, SHALL be rejected with the item names.

#### Scenario: Missing recipe
- **WHEN** an order contains a prepared item that has no recipe
- **THEN** completion is rejected naming that item

### Requirement: Deduction is atomic with completion
Stock deduction, line cost capture, payment checks, and the status change SHALL commit together or not at all; a failure SHALL leave no movements and the order not completed.

#### Scenario: Failure midway
- **WHEN** a database error occurs after some movements are written
- **THEN** no movements remain and the order is not completed

### Requirement: Deduction is not repeated
Each completed order SHALL produce its sale-consumption movements once; repeated or concurrent completion requests SHALL NOT create additional movements.

#### Scenario: Duplicate completion
- **WHEN** two completion requests for the same order arrive at the same time
- **THEN** exactly one set of movements exists

### Requirement: Insufficient stock blocks completion by default
When negative stock is disallowed, completion SHALL be rejected if any required quantity exceeds available quantity, and the response SHALL list each short item with required and available quantities. Concurrent orders SHALL NOT oversell.

#### Scenario: Not enough milk
- **WHEN** an order needs 300 ml milk and 200 ml is available
- **THEN** completion is rejected listing milk required 300 ml, available 200 ml

#### Scenario: Concurrent last servings
- **WHEN** two orders each needing the last 18 g of beans complete at the same time
- **THEN** exactly one succeeds and the other is rejected for insufficient stock

### Requirement: Negative stock when allowed
When negative stock is allowed, completion SHALL proceed, resulting negative balances SHALL be recorded, and affected movements and order lines SHALL be flagged as cost-uncertain.

#### Scenario: Allowed negative
- **WHEN** negative stock is allowed and an order needs 300 ml milk with 200 ml available
- **THEN** completion succeeds, milk shows -100 ml, and the line is flagged cost-uncertain

### Requirement: Cost captured per line
Each sale-consumption movement SHALL reference the order and line, and each completed line SHALL record the recipe or stock-link version used and its cost of goods sold at the weighted-average cost at completion.

#### Scenario: Line COGS
- **WHEN** an iced milk coffee is completed with ingredient costs totalling 10200 VND
- **THEN** that line records COGS 10200 and the recipe version id

### Requirement: History is never reprocessed
Recipe, stock-link, or cost changes SHALL NOT modify movements or line costs of already completed orders.

#### Scenario: Recipe changed after sale
- **WHEN** a recipe changes after an order was completed
- **THEN** the order's movements and COGS are unchanged

### Requirement: Explicit returns to stock
Users with return permission SHALL return direct-sale items from a completed order to stock, up to the quantity sold minus earlier returns, with a reason and sellable flag; only sellable returns SHALL post return movements at the line's original unit cost. Returns SHALL be idempotent and independent of refunds.

#### Scenario: Unopened bottle returned
- **WHEN** a manager returns 1 unopened bottled water as sellable
- **THEN** a return movement of +1 bottle referencing the order is posted

#### Scenario: Prepared item return
- **WHEN** a user attempts to return a prepared drink to stock
- **THEN** the system rejects it

#### Scenario: Cancelled draft
- **WHEN** a draft order is cancelled
- **THEN** no stock changes occur
