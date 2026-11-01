# Spec Delta

## ADDED Requirements

### Requirement: Owners configure POS fee types under Admin
The system SHALL let owners and superusers create and manage named fee types under Admin, including enabling or disabling each type for POS use. Fee configuration changes SHALL be audited, and disabling a fee type SHALL NOT change fees already applied to orders.

#### Scenario: Owner enables a shipping fee
- **WHEN** an owner creates and enables a fee type named "Shipping"
- **THEN** the fee type is available for cashier entry on the POS

#### Scenario: Owner disables a fee type
- **WHEN** an owner disables a fee type
- **THEN** it is no longer available for new POS charges and existing order fee snapshots remain unchanged

#### Scenario: Non-owner manages fee types
- **WHEN** a user without owner permissions attempts to create, edit, enable, or disable a fee type
- **THEN** the system rejects the request without changing fee configuration

### Requirement: Shop name is managed under Admin
The system SHALL let owners and superusers edit the shop name under Admin, use it on printed receipts, and no longer offer its editor under Settings → Business.

#### Scenario: Owner changes the receipt shop name
- **WHEN** an owner saves a new shop name under Admin
- **THEN** subsequent receipts show the saved name

#### Scenario: Non-owner changes the shop name
- **WHEN** a user without owner permissions attempts to change the shop name
- **THEN** the system rejects the change

### Requirement: VAT rate is managed under Admin
The system SHALL let owners and superusers configure the existing global VAT rate under Admin. The configured rate SHALL apply to tax-inclusive product prices and all configured POS fees, retain the existing 0–100 percent range and two-decimal precision, and be audited. The VAT rate SHALL no longer be editable under Settings → Business. Changing the rate SHALL affect new orders only; existing orders SHALL retain their saved tax-rate snapshot.

#### Scenario: Owner changes the global VAT rate
- **WHEN** an owner saves a valid VAT rate under Admin
- **THEN** the saved rate is audited and used for new orders and POS fees

#### Scenario: Invalid VAT rate is rejected
- **WHEN** an owner submits a VAT rate outside 0–100 percent or with more than two decimal places
- **THEN** the system rejects the update without changing the configured rate

#### Scenario: Existing order keeps its VAT snapshot
- **WHEN** an owner changes the configured VAT rate after an order was created
- **THEN** the existing order retains its saved tax rate and tax calculation

#### Scenario: Non-owner changes the VAT rate
- **WHEN** a user without owner permissions attempts to change the VAT rate
- **THEN** the system rejects the change
