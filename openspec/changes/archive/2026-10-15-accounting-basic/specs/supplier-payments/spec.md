# Spec Delta

## Purpose

Records payments to suppliers against posted stock receipts so that amounts owed are always known and receiving stock stays separate from paying for it.

## ADDED Requirements

### Requirement: Pay supplier payables
Users with supplier payment permission SHALL record a payment to a supplier with amount greater than zero, payment date, money account, optional reference, and allocations to one or more of that supplier's open payables. Allocations SHALL sum to the payment amount.

#### Scenario: Partial payment
- **WHEN** an accountant pays 1,000,000 VND against a 2,000,000 VND receipt payable
- **THEN** the receipt is partially_paid with 1,000,000 VND outstanding

#### Scenario: Pay across receipts
- **WHEN** a payment of 1,500,000 VND is allocated 1,000,000 and 500,000 to two receipts
- **THEN** both payables reflect their allocations

### Requirement: No overpayment of payables
An allocation SHALL NOT exceed the payable's outstanding amount, and allocations SHALL only target the paying supplier's posted payables.

#### Scenario: Over-allocation
- **WHEN** a user allocates 600,000 VND to a payable with 500,000 VND outstanding
- **THEN** the system rejects the payment

### Requirement: Default allocation
When no allocations are given, the system SHALL allocate the payment to the supplier's open payables oldest first.

#### Scenario: Auto allocate
- **WHEN** a 700,000 VND payment is recorded without allocations against payables of 500,000 and 400,000
- **THEN** 500,000 goes to the older and 200,000 to the newer payable

### Requirement: Payment at receipt posting
When a stock receipt is posted with an immediate payment amount and account, the system SHALL record a supplier payment allocated to that receipt in the same transaction.

#### Scenario: Pay on delivery
- **WHEN** a receipt of 2,000,000 VND is posted with immediate cash payment of 2,000,000 VND
- **THEN** the receipt is paid and a cash outflow is recorded

### Requirement: Supplier payments are idempotent and reversible
Supplier payments SHALL require an idempotency key. Posted payments SHALL NOT be edited or deleted; a reversal SHALL restore the allocated outstanding amounts and record an opposite money movement.

#### Scenario: Reverse payment
- **WHEN** a supplier payment is reversed
- **THEN** the related payables' outstanding amounts return to their prior values

### Requirement: Payables are distinct from purchases
Supplier balances SHALL show purchases (posted receipts), payments, and outstanding amount separately, and purchase history SHALL list payments distinctly from receipts.

#### Scenario: Supplier statement
- **WHEN** a user views a supplier's statement
- **THEN** receipts and payments appear as separate entries with a running outstanding balance
