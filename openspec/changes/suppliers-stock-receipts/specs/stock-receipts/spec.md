# Spec Delta

## Purpose

Records goods received from suppliers so that stock, inventory valuation, and supplier payables increase together and remain traceable.

## ADDED Requirements

### Requirement: Draft receipts
Users with purchasing management permission SHALL create and edit draft receipts with a unique reference, supplier, receipt date, notes, and lines of item, purchase quantity greater than zero, and purchase unit cost greater than or equal to zero. Drafts SHALL NOT affect stock, valuation, or payables.

#### Scenario: Save draft
- **WHEN** a user saves a draft receipt for 5 kg coffee beans
- **THEN** coffee bean quantity is unchanged

#### Scenario: Duplicate reference
- **WHEN** a user saves a receipt whose reference already exists
- **THEN** the system rejects it with a conflict error

### Requirement: Totals calculated by the system
Line totals SHALL equal purchase quantity times purchase unit cost and the receipt total SHALL equal the sum of line totals, computed by the backend.

#### Scenario: Client total ignored
- **WHEN** a client submits a receipt with an incorrect total
- **THEN** the stored total equals the computed sum of lines

### Requirement: Posting a receipt
Posting SHALL validate the receipt, convert each line to base units using the item's conversion factor, post receipt movements valued at base-unit cost, update weighted-average cost, record a supplier payable equal to the receipt total, record the posting user and time, and set status posted, all atomically.

#### Scenario: Post coffee receipt
- **WHEN** a receipt of 5 kg coffee beans at 400,000 VND/kg is posted for an item with factor 1000
- **THEN** quantity increases by 5000 g at 400 VND/g and a payable of 2,000,000 VND is recorded for the supplier

#### Scenario: Inactive item on posting
- **WHEN** a draft contains an item that was deactivated
- **THEN** posting is rejected and nothing changes

### Requirement: Posting is idempotent and one-time
Posting SHALL require an idempotency key; a repeated request SHALL NOT post twice, and posting a receipt that is not a draft SHALL be rejected.

#### Scenario: Double click on post
- **WHEN** the post request is sent twice with the same key
- **THEN** stock increases once

#### Scenario: Post already posted receipt
- **WHEN** a user posts a receipt that is already posted with a new key
- **THEN** the system rejects it with a conflict error

### Requirement: Posted receipts are immutable
Posted or reversed receipts SHALL NOT be edited or deleted. Draft receipts MAY be deleted.

#### Scenario: Edit posted receipt
- **WHEN** a user edits a line of a posted receipt
- **THEN** the system rejects the change

### Requirement: Receipt reversal
Users with reversal permission SHALL reverse a posted receipt with a reason; reversal SHALL post opposite movements at the original costs, reduce the supplier payable, link to the original, and set status reversed. Reversal SHALL be rejected if any payment has been applied to the receipt or if stock would become negative while negative stock is disallowed.

#### Scenario: Reverse unpaid receipt
- **WHEN** a manager reverses an unpaid posted receipt with enough stock remaining
- **THEN** stock and payable return to their prior values and both receipts show the link

#### Scenario: Reverse paid receipt
- **WHEN** a manager reverses a receipt with an applied payment
- **THEN** the system rejects the reversal

### Requirement: Payment status
Each posted receipt SHALL show payment status unpaid, partially_paid, or paid derived from payments applied to its payable.

#### Scenario: New posted receipt
- **WHEN** a receipt is posted with no payments
- **THEN** its payment status is unpaid
