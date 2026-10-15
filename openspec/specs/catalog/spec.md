# catalog Specification

## Purpose

Defines what the business sells: menu categories and menu items with their product type, current selling price, availability, and an auditable change history.

## Requirements

### Requirement: Manage menu categories
Users with catalog management permission SHALL create, rename, reorder, and deactivate menu categories. Category names SHALL be unique among active categories.

#### Scenario: Create category
- **WHEN** a manager creates category "Cà phê"
- **THEN** the category is listed and selectable for menu items

#### Scenario: Duplicate category name
- **WHEN** a manager creates a second active category named "Cà phê"
- **THEN** the system rejects it with a conflict error

### Requirement: Menu item attributes
A menu item SHALL have a unique product code, name, optional description, category, selling price in VND greater than or equal to zero, product type (prepared, direct_sale, non_stock), active flag, available flag, and optional image.

#### Scenario: Create prepared drink
- **WHEN** a manager creates "Cà phê sữa đá" with type prepared, price 29000
- **THEN** the item is saved with those values and a system-assigned code, and is active and available

#### Scenario: Negative price rejected
- **WHEN** a manager submits a selling price of -1000
- **THEN** the system rejects the item with a validation error

### Requirement: Product codes are system-assigned
The system SHALL assign each new menu item the next code in the format `MENU-` followed by a zero-padded sequence number of at least five digits (MENU-00001, MENU-00002, ...). Codes SHALL be unique, SHALL NOT be supplied by the client, and SHALL NOT change after creation. Numbers are never reused, so gaps MAY appear.

#### Scenario: Sequential codes
- **WHEN** a manager creates two menu items in a row and the last assigned code was MENU-00007
- **THEN** the items receive MENU-00008 and MENU-00009

#### Scenario: Code cannot be edited
- **WHEN** a manager submits an update for MENU-00008 that includes a different code
- **THEN** the item keeps code MENU-00008

### Requirement: Price and attribute changes are audited
Changes to a menu item's price, name, product type, active flag, or available flag SHALL create an audit entry with old and new values.

#### Scenario: Price change history
- **WHEN** a manager changes MENU-00001's price from 29000 to 32000
- **THEN** an audit entry records the change and the item's current price is 32000

### Requirement: Sold items cannot be deleted
A menu item that appears on any order SHALL NOT be deletable; it MAY only be deactivated. Items never sold MAY be deleted.

#### Scenario: Delete sold item
- **WHEN** a manager deletes an item that appears on a completed order
- **THEN** the system rejects the deletion and suggests deactivation

### Requirement: Only active and available items are sellable
Inactive or unavailable menu items SHALL NOT be addable to new orders and SHALL be hidden from the POS menu by default.

#### Scenario: Mark item sold out
- **WHEN** a manager marks an item unavailable
- **THEN** the POS menu no longer offers it and adding it to an order is rejected

### Requirement: Search and filter menu items
Users who can view the catalog SHALL search items by name or code and filter by category, product type, and active status, with paginated results.

#### Scenario: Search by partial name
- **WHEN** a cashier searches "sữa"
- **THEN** all active items whose name contains "sữa" are returned

### Requirement: Optional item image
Users with catalog management permission SHALL be able to upload one JPEG, PNG, or WebP image of at most 2 MB per menu item.

#### Scenario: Oversized image
- **WHEN** a manager uploads a 5 MB image
- **THEN** the system rejects it and the item keeps its previous image
