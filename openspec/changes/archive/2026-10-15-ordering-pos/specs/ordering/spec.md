# Spec Delta

## Purpose

Lets staff build and finalize customer orders through a point-of-sale interface, with backend-owned totals, a validated lifecycle, and historical snapshots of what was sold and at what price.

## ADDED Requirements

### Requirement: Create orders
Users with order creation permission SHALL create an order of type counter, takeaway, or dine_in (with optional table label). The system SHALL assign a unique order number, the creating cashier, and status draft.

#### Scenario: New takeaway order
- **WHEN** a cashier starts a takeaway order
- **THEN** a draft order with a unique number and the cashier recorded is created

### Requirement: Manage order lines on open orders
While an order is draft or confirmed, users SHALL add active available menu items, change quantities, remove lines, and edit notes. Quantities SHALL be positive with at most three decimals; other statuses SHALL reject line changes.

#### Scenario: Add item
- **WHEN** a cashier adds 2 of "Cà phê sữa đá" priced 29000
- **THEN** a line with quantity 2 and line total 58000 is added

#### Scenario: Zero quantity rejected
- **WHEN** a cashier sets a line quantity to 0
- **THEN** the system rejects the change

#### Scenario: Unavailable item rejected
- **WHEN** a cashier adds an item marked unavailable
- **THEN** the system rejects it

#### Scenario: Edit completed order
- **WHEN** a user adds a line to a completed order
- **THEN** the system rejects the change

### Requirement: Line snapshots
Each line SHALL store the menu item id, item name, unit price, quantity, discount, tax rate, tax amount, and line total as of when the line was added or last changed while open. Later catalog changes SHALL NOT alter existing lines of completed or cancelled orders.

#### Scenario: Price change after sale
- **WHEN** an item's price changes from 29000 to 32000 after an order with that item was completed
- **THEN** the completed order still shows 29000 and its original total

### Requirement: Backend-calculated totals
The backend SHALL compute line totals, subtotal, discount total, tax total, and order total, ignoring any totals sent by clients. Prices SHALL be tax-inclusive, and tax amounts SHALL be derived from the configured tax rate (default 0%).

#### Scenario: Totals returned
- **WHEN** an order has lines 58000 and 35000 and an order discount of 10%
- **THEN** subtotal is 93000, discount 9300, and total 83700

### Requirement: Authorized discounts
Line and order discounts SHALL be expressed as an amount or a percentage between 0 and 100, SHALL NOT exceed the amount they apply to, and SHALL require discount permission. Each discount SHALL record who applied it.

#### Scenario: Cashier without permission
- **WHEN** a cashier without discount permission applies a 20% discount
- **THEN** the system responds with 403

#### Scenario: Discount exceeds total
- **WHEN** a manager applies a 50000 discount to a 30000 line
- **THEN** the system rejects it

### Requirement: Validated lifecycle
Order status SHALL be one of draft, confirmed, paid, completed, cancelled, partially_refunded, refunded. The backend SHALL allow only: draft to confirmed; draft or confirmed to cancelled; draft, confirmed, or paid to completed; transitions to paid and refund states only through payment operations. Any other transition SHALL be rejected.

#### Scenario: Invalid transition
- **WHEN** a client requests cancelling a completed order
- **THEN** the system rejects it with a conflict error and the status is unchanged

### Requirement: Completion is final and single
Completing an order SHALL require at least one line, SHALL record completion time and user, and SHALL NOT be processable twice; repeated completion requests with the same idempotency key SHALL return the original result.

#### Scenario: Double completion
- **WHEN** completion is requested twice for the same order
- **THEN** the order is completed once and the second request causes no further effect

#### Scenario: Empty order
- **WHEN** a cashier completes an order with no lines
- **THEN** the system rejects it

### Requirement: Cancellation
Users with cancel permission SHALL cancel draft or confirmed orders with a reason. Cancelled orders SHALL keep their lines for history and SHALL NOT count as sales.

#### Scenario: Cancel draft
- **WHEN** a cashier cancels a draft order with reason "customer left"
- **THEN** the order is cancelled and excluded from sales

### Requirement: Receipt output
For confirmed and later orders, the system SHALL provide a printable receipt showing business name, order number, date and time in business timezone, lines, discounts, tax, total in VND, and cashier.

#### Scenario: Print receipt
- **WHEN** a cashier opens the receipt of a completed order
- **THEN** a print-ready view with the snapshot values is shown

### Requirement: Order history
Users SHALL search orders by number, date range, status, order type, and cashier, newest first and paginated. Cashiers with only own-history permission SHALL see only their own orders.

#### Scenario: Cashier scope
- **WHEN** a cashier lists order history
- **THEN** only orders created by that cashier are returned

### Requirement: POS usability
The POS interface SHALL let a cashier search and add items, adjust quantities, and complete an order on screens 768 px wide or larger, and SHALL display backend validation messages.

#### Scenario: Tablet layout
- **WHEN** the POS is opened on a 768 px wide screen
- **THEN** menu, cart, and totals are usable without horizontal scrolling
