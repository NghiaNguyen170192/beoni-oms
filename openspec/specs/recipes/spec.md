# recipes Specification

## Purpose

Defines how much of each inventory item one unit of a menu item consumes, with versioning so recipe changes affect only future sales.

## Requirements

### Requirement: Recipes for prepared items
Users with recipe management permission SHALL define a recipe for a prepared menu item as lines of active inventory item and quantity per serving greater than zero, expressed in that inventory item's base unit. An inventory item SHALL appear at most once per recipe version.

#### Scenario: Iced milk coffee recipe
- **WHEN** a manager defines 18 g coffee beans, 30 ml condensed milk, 150 g ice, 1 cup for "Cà phê sữa đá"
- **THEN** the recipe is saved with those lines in base units

#### Scenario: Recipe on non-prepared item
- **WHEN** a manager adds a recipe to a non_stock item
- **THEN** the system rejects it

### Requirement: Recipe versions
Saving a changed recipe SHALL create a new version with an effective-from timestamp; earlier versions SHALL remain unchanged and readable. Exactly one version SHALL be applicable at any point in time.

#### Scenario: Change quantity
- **WHEN** a manager changes coffee beans from 18 g to 20 g effective now
- **THEN** version 2 is created and version 1 still shows 18 g

#### Scenario: Future effective date
- **WHEN** a manager saves version 3 effective tomorrow
- **THEN** sales completed today use version 2

### Requirement: Direct-sale stock link
A direct_sale menu item SHALL be linked to exactly one active inventory item and a quantity per unit sold (default 1), and the link SHALL be versioned like recipes.

#### Scenario: Bottled water
- **WHEN** a manager links "Nước suối" to inventory item "Aquafina 500ml" with quantity 1
- **THEN** each unit sold consumes one bottle

### Requirement: Recipe changes are audited
Creating a recipe version or stock link version SHALL record an audit entry with the previous and new lines.

#### Scenario: Audit on change
- **WHEN** a recipe version is created
- **THEN** an audit entry lists the old and new lines

### Requirement: Recipe cost preview
The system SHALL show each recipe version's estimated cost per serving from current average costs, and SHALL flag lines whose cost is unknown.

#### Scenario: Cost preview
- **WHEN** coffee beans average 400 VND/g and the recipe uses 18 g plus other lines costing 3000
- **THEN** the estimated cost per serving is 10200 VND
