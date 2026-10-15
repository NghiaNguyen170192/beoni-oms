# idempotency Specification

## Purpose

Guarantees that retried or duplicated requests for critical operations (order completion, payments, refunds, receipt posting, stock adjustments, supplier payments) take effect at most once.

## Requirements

### Requirement: Critical operations require an idempotency key
Endpoints designated as critical SHALL require an `Idempotency-Key` header and reject requests without one.

#### Scenario: Missing key
- **WHEN** a client calls a critical endpoint without an Idempotency-Key header
- **THEN** the system responds with 400 and performs no action

### Requirement: Repeated keys return the original result
A request reusing a key already completed within the same operation scope SHALL return the original response status and body without performing the operation again.

#### Scenario: Retried payment
- **WHEN** a client sends the same payment request twice with the same key
- **THEN** both responses describe the same single payment and only one payment exists

### Requirement: Key reuse with a different payload is rejected
Reusing a key within the same scope with a different request payload SHALL be rejected with 422 and no side effects.

#### Scenario: Same key, different amount
- **WHEN** a client reuses a payment key with a different amount
- **THEN** the system responds with 422 and no new payment is recorded

### Requirement: Concurrent duplicates are processed once
When two requests with the same key arrive concurrently, exactly one SHALL perform the operation and the other SHALL receive the same result or a 409 asking the client to retry.

#### Scenario: Simultaneous duplicates
- **WHEN** two identical requests with the same key are processed at the same time
- **THEN** exactly one business transaction is created

### Requirement: Failed operations do not consume the key
If the operation fails and is rolled back, the key SHALL NOT be stored, so a corrected retry with the same key can succeed.

#### Scenario: Retry after failure
- **WHEN** an order completion fails for insufficient stock and is retried with the same key after stock is received
- **THEN** the retry is processed normally
