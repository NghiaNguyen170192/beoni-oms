# suppliers Specification

## Purpose

Keeps the list of suppliers the business buys from, with contact details, purchase history, and how much is still owed to each.

## Requirements

### Requirement: Manage suppliers
Users with purchasing management permission SHALL create, edit, and deactivate suppliers with name, optional code, phone, email, address, tax code, contact person, and notes. Supplier codes SHALL be unique when provided.

#### Scenario: Create supplier
- **WHEN** inventory staff create supplier "Trung Nguyên" with a phone number
- **THEN** the supplier is available for new receipts

#### Scenario: Deactivated supplier
- **WHEN** a supplier is deactivated
- **THEN** it cannot be selected for new receipts but its history remains visible

### Requirement: Supplier purchase history
Users with purchasing view permission SHALL see a supplier's receipts with reference, date, total, status, and payment status, filterable by date range.

#### Scenario: View history
- **WHEN** a user opens a supplier with three posted receipts
- **THEN** all three receipts are listed with their totals

### Requirement: Outstanding balance per supplier
The system SHALL show for each supplier the total posted payables, total paid, and outstanding balance, derived from recorded transactions.

#### Scenario: Unpaid receipts
- **WHEN** a supplier has two posted unpaid receipts of 1,000,000 and 500,000 VND
- **THEN** the outstanding balance is 1,500,000 VND

### Requirement: Suppliers with history cannot be deleted
A supplier referenced by any receipt SHALL NOT be deleted; it MAY only be deactivated.

#### Scenario: Delete supplier with receipts
- **WHEN** a user deletes a supplier with receipts
- **THEN** the system rejects the deletion
