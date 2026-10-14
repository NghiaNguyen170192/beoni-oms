# Spec Delta

## Purpose

Lets authorized staff correct stock for counts, spoilage, expiry, damage, loss, or data errors while leaving a complete, traceable record.

## ADDED Requirements

### Requirement: Authorized reason-coded adjustments
Users with adjustment permission SHALL post adjustments for one or more items with a reason of physical_count, spoilage, expired, damaged, missing, or correction, and an optional note.

#### Scenario: Spoilage
- **WHEN** inventory staff post a spoilage adjustment of -500 ml milk
- **THEN** milk quantity decreases by 500 ml and an adjustment movement is recorded

#### Scenario: Cashier denied
- **WHEN** a cashier posts an adjustment
- **THEN** the system responds with 403

### Requirement: Adjustment records previous, change, and result
Each adjustment line SHALL store the previous quantity, the change, the resulting quantity, the reason, the timestamp, and the responsible user.

#### Scenario: Recorded values
- **WHEN** coffee beans at 2000 g are adjusted by -100 g
- **THEN** the line records previous 2000, change -100, result 1900

### Requirement: Physical count sets the counted quantity
A physical_count line SHALL accept the counted quantity and post the difference from the current quantity, computed by the system at posting time.

#### Scenario: Count lower than system
- **WHEN** the system shows 1900 g and staff count 1850 g
- **THEN** a movement of -50 g is posted and the result is 1850 g

### Requirement: Adjustment valuation
Decreases SHALL be valued at the current average cost. Increases SHALL use a unit cost entered by the user or, if none is entered, the current average cost.

#### Scenario: Increase without cost
- **WHEN** a correction adds 100 g with no unit cost entered
- **THEN** the movement uses the current average cost and the average is unchanged

### Requirement: Adjustments are atomic and idempotent
Posting an adjustment SHALL apply all lines or none, and repeating the request with the same idempotency key SHALL NOT post it twice.

#### Scenario: One invalid line
- **WHEN** an adjustment with two lines has one line referencing an inactive item
- **THEN** no line is applied

#### Scenario: Duplicate submission
- **WHEN** the same adjustment is submitted twice with the same key
- **THEN** only one set of movements exists

### Requirement: Negative result follows the stock policy
An adjustment that would make a quantity negative SHALL be rejected unless negative stock is allowed in business settings.

#### Scenario: Negative not allowed
- **WHEN** negative stock is disallowed and an adjustment would leave -10 g
- **THEN** the adjustment is rejected

### Requirement: Posted adjustments are corrected by reversal
Posted adjustments SHALL NOT be edited or deleted; a reversal SHALL post equal and opposite movements linked to the original.

#### Scenario: Reverse adjustment
- **WHEN** a manager reverses a -100 g adjustment
- **THEN** a +100 g reversal movement linked to the original is posted and the original is marked reversed
