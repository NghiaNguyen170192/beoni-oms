# cash-movements Specification

## Purpose

Shows money recorded as moving into and out of the business's cash drawer and bank accounts, derived from payments, refunds, supplier payments, expenses, and authorized adjustments.

## Requirements

### Requirement: Money accounts
The system SHALL maintain money accounts of kind cash or bank, with defaults "Cash drawer" and "Bank". Each payment method SHALL map to one money account.

#### Scenario: Method mapping
- **WHEN** a customer pays by bank transfer
- **THEN** the resulting inflow is recorded on the account mapped to bank transfer

### Requirement: Every money event creates a movement
Customer payments, voids, refunds, supplier payments and their reversals, paid expenses and their reversals, and cash adjustments SHALL each create a signed money movement with account, amount, date, source type and id, and actor, in the same transaction as the source event.

#### Scenario: Refund outflow
- **WHEN** a 29000 cash refund is recorded
- **THEN** a -29000 movement on Cash drawer referencing the refund exists

#### Scenario: Voided payment
- **WHEN** a payment is voided
- **THEN** an opposite movement referencing the void is recorded

### Requirement: Authorized cash adjustments
Users with cash adjustment permission SHALL record a cash adjustment on an account with signed amount and required reason; adjustments are idempotent and corrected only by reversal.

#### Scenario: Opening float
- **WHEN** an owner records +500,000 VND "opening float" on Cash drawer
- **THEN** the account balance increases by 500,000 VND

### Requirement: Recorded balances are labelled as unreconciled
Account balances SHALL equal the sum of their movements and SHALL be presented as recorded balances, not bank-reconciled balances.

#### Scenario: Balance display
- **WHEN** a user views account balances
- **THEN** each balance equals its movement sum and is labelled "recorded"

### Requirement: Movement review
Users with cash view permission SHALL list movements by account, date range, and source type, with opening balance, inflows, outflows, and closing balance for the period.

#### Scenario: Daily cash review
- **WHEN** a manager reviews today's Cash drawer movements
- **THEN** opening + inflows - outflows equals closing
