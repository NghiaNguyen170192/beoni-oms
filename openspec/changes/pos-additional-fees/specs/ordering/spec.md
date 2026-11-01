# Spec Delta

## MODIFIED Requirements

### Requirement: Backend-calculated totals
The backend SHALL compute line totals, subtotal, discount total, tax total, fee total, and order total, ignoring any totals sent by clients. Product prices and configured order fee amounts SHALL be VAT-inclusive. The backend SHALL extract VAT embedded in fees using the order's configured tax-rate snapshot and include it in tax total. The configured global VAT rate SHALL be snapshotted when an order is created; subsequent setting changes SHALL NOT alter existing orders. Fees SHALL remain outside product subtotal and discounts, and order total SHALL equal subtotal minus discounts plus fees.

#### Scenario: Totals returned
- **WHEN** an order has lines 58000 and 35000 and an order discount of 10%
- **THEN** subtotal is 93000, discount 9300, and total before fees is 83700

#### Scenario: VAT-inclusive fee added
- **WHEN** the order above has a configured additional fee of 5000 and the business tax rate is 10%
- **THEN** the fee total is 5000, 455 of embedded VAT is included in tax total, and the order total remains 88700

## ADDED Requirements

### Requirement: Cashiers can enter configured fees on open orders
The system SHALL show enabled fee types on the POS and allow users with order creation permission to enter a non-negative VND amount for each fee on an open order. Entered fee amounts SHALL include VAT at the order's configured tax-rate snapshot. Zero-value fees SHALL be omitted from the order; fees SHALL NOT be included in product subtotal or discounts.

#### Scenario: Cashier adds a shipping fee
- **WHEN** a cashier enters a 25000 shipping fee on an open order
- **THEN** the 25000 fee, including its embedded VAT, is included in the backend-calculated order total and displayed separately from products

#### Scenario: Zero fee omitted
- **WHEN** a cashier leaves an enabled fee at zero
- **THEN** the order has no applied fee for that fee type and its total is unchanged

#### Scenario: Disabled fee cannot be newly applied
- **WHEN** a cashier submits an amount for a disabled or unknown fee type not already applied to the order
- **THEN** the system rejects the order change and preserves the existing order

#### Scenario: Existing disabled fee is retained or removed
- **WHEN** a fee type is disabled after its fee was applied to an open order
- **THEN** the existing snapshot remains on that order, the cashier may leave it unchanged or remove it, and the cashier cannot increase or reapply it

#### Scenario: Invalid fee amount rejected
- **WHEN** a cashier submits a negative or invalid-precision fee amount
- **THEN** the system rejects the order change and preserves the existing order

### Requirement: Order fees are preserved as snapshots
The system SHALL preserve each applied fee's name and amount on the order so later changes to its configuration do not alter existing orders. Fees SHALL be editable only while the order is open and SHALL be shown in order details and receipts.

#### Scenario: Fee configuration renamed after completion
- **WHEN** an owner renames a fee type after an order using it is completed
- **THEN** the completed order and receipt retain the original fee name and amount

#### Scenario: Completed fee cannot be edited
- **WHEN** a user attempts to change a fee on a completed order
- **THEN** the system rejects the change and leaves the completed order unchanged
