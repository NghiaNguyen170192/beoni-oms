# Spec Delta

## Purpose

Records money received for orders and money returned to customers, exactly once and linked to the originating sale, without treating payments as additional revenue.

## ADDED Requirements

### Requirement: Configurable payment methods
Owners SHALL manage payment methods with name, kind (cash, bank_transfer, other), and active flag. Cash and bank transfer SHALL exist by default. Inactive methods SHALL NOT be usable for new payments.

#### Scenario: Add method
- **WHEN** an owner adds method "MoMo" of kind other
- **THEN** cashiers can select MoMo for new payments

#### Scenario: Inactive method
- **WHEN** a cashier pays with an inactive method
- **THEN** the system rejects the payment

### Requirement: Record payments
Users with payment permission SHALL record payments on draft, confirmed, or paid orders with amount greater than zero, method, optional reference, and the recording user and time. An order MAY have multiple payments.

#### Scenario: Split payment
- **WHEN** a cashier records 50000 cash and 33700 bank transfer on an 83700 order
- **THEN** two payments exist and the order's paid amount is 83700

### Requirement: Cash tender and change
For cash payments the user MAY enter the tendered amount; the system SHALL record the tendered amount and change, and the payment amount SHALL equal tendered minus change.

#### Scenario: Change due
- **WHEN** a cashier enters 100000 tendered for a remaining 83700
- **THEN** a payment of 83700 is recorded with change 16300

### Requirement: No overpayment
Non-cash payments SHALL NOT make total paid exceed the order total.

#### Scenario: Bank overpayment
- **WHEN** a cashier records a 90000 bank transfer on an 83700 unpaid order
- **THEN** the system rejects the payment

### Requirement: Payments are idempotent
Payment recording SHALL require an idempotency key, and repeated requests with the same key SHALL NOT create additional payments.

#### Scenario: Retry after timeout
- **WHEN** a payment request is retried with the same key
- **THEN** only one payment exists

### Requirement: Paid status
When active payments on an unfinished order cover its total, the order status SHALL become paid; if a void reduces coverage, the order SHALL return to confirmed.

#### Scenario: Fully paid
- **WHEN** payments reach the order total
- **THEN** the order status is paid

### Requirement: Completion requires full payment
Completing an order SHALL be rejected unless active payments cover its total. A pay-and-complete operation SHALL record the payment and complete the order atomically.

#### Scenario: Unpaid completion
- **WHEN** a cashier completes an order with 50000 paid of 83700
- **THEN** the system rejects completion and shows the remaining amount

#### Scenario: Pay and complete
- **WHEN** a cashier uses pay-and-complete with cash for the full total
- **THEN** the payment is recorded and the order is completed in one step

### Requirement: Void payments before completion
Users with void permission SHALL void a payment on an order that is not completed, with a reason. Voided payments SHALL remain visible and SHALL NOT count toward paid amount. Payments of completed orders SHALL NOT be voided.

#### Scenario: Void on completed order
- **WHEN** a manager voids a payment of a completed order
- **THEN** the system rejects it and directs the user to a refund

### Requirement: Refunds on completed orders
Users with refund permission SHALL record a refund on a completed or partially refunded order with amount, method, reason, optional line references, and actor. Total refunds SHALL NOT exceed total paid.

#### Scenario: Partial refund
- **WHEN** a manager refunds 29000 of an 83700 order
- **THEN** a refund linked to the order exists and the order status is partially_refunded

#### Scenario: Over-refund
- **WHEN** refunds would exceed the amount paid
- **THEN** the system rejects the refund

#### Scenario: Full refund
- **WHEN** refunds reach the amount paid
- **THEN** the order status is refunded

### Requirement: Refunds are idempotent and do not change stock
Refunds SHALL require an idempotency key and SHALL NOT post inventory movements.

#### Scenario: Refund prepared drink
- **WHEN** a refund is recorded for a prepared drink
- **THEN** no ingredient quantity changes

### Requirement: Payment and refund review
Users with payment view permission SHALL list payments and refunds filtered by date range, method, status, cashier, and order, with totals per method.

#### Scenario: Daily cash total
- **WHEN** a manager filters today's payments by cash
- **THEN** the list and the cash total reflect only today's active cash payments minus cash refunds
