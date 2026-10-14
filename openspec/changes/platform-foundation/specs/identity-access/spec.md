# Spec Delta

## Purpose

Controls who can do what in Beoni OMS by assigning each user one business role and enforcing that role's permissions on every protected backend operation.

## ADDED Requirements

### Requirement: Users have exactly one business role
Every user SHALL have exactly one role from: owner, manager, cashier, inventory_staff, accountant. Superusers SHALL be treated as owner. New users default to cashier unless an owner chooses otherwise.

#### Scenario: Owner assigns a role
- **WHEN** an owner updates a user's role to inventory_staff
- **THEN** the user's subsequent requests are authorized with inventory_staff permissions

#### Scenario: Invalid role rejected
- **WHEN** an owner submits a role value that is not in the allowed list
- **THEN** the system rejects the request with a validation error and the role is unchanged

#### Scenario: Only owners manage roles
- **WHEN** a manager attempts to change any user's role
- **THEN** the system responds with 403 and the role is unchanged

### Requirement: Permission matrix
The system SHALL grant permissions per role: owner has all; manager has catalog, inventory, purchasing, ordering, payments, recipes, expenses, and sales reports; cashier has ordering, payments, and own sales history; inventory_staff has inventory, purchasing, and inventory reports; accountant has read access to sales, payments, purchasing, and all reports plus expenses and supplier payments.

#### Scenario: Cashier cannot adjust stock
- **WHEN** a cashier calls the stock adjustment endpoint
- **THEN** the system responds with 403 and no adjustment is recorded

#### Scenario: Accountant reads financial reports
- **WHEN** an accountant requests the profit report
- **THEN** the system returns the report

### Requirement: Backend enforces authorization on every protected route
Every non-public API route SHALL require authentication and the specific permission for its action, regardless of what the frontend shows.

#### Scenario: Unauthenticated request
- **WHEN** a request without a valid token calls a protected route
- **THEN** the system responds with 401 or 403 and performs no action

#### Scenario: Direct API call bypassing UI
- **WHEN** a cashier sends a request directly to an owner-only endpoint
- **THEN** the system responds with 403

### Requirement: Current user permissions are discoverable
The system SHALL return the authenticated user's role and permission list so clients can show only permitted navigation and actions.

#### Scenario: Sidebar reflects role
- **WHEN** an inventory_staff user loads the application
- **THEN** navigation shows inventory and purchasing pages and hides POS, expenses, and user administration

### Requirement: Passwords and sessions are protected
Passwords SHALL be stored only as strong salted hashes, and inactive users SHALL be unable to authenticate or use existing tokens.

#### Scenario: Deactivated user token rejected
- **WHEN** an owner deactivates a user who holds a valid token
- **THEN** the next request with that token is rejected
