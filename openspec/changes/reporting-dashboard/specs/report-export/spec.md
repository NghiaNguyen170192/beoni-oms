# Spec Delta

## Purpose

Lets authorized users download report data as CSV files that exactly match what the report shows for the same filters.

## ADDED Requirements

### Requirement: CSV export per report
Sales summary, product performance, inventory movement summary, expense breakdown, profit statement, payments list, and income listing SHALL each offer CSV export.

#### Scenario: Export sales summary
- **WHEN** a manager exports the sales summary
- **THEN** a CSV file downloads with one row per period group and a header row

### Requirement: Export matches filters
An export SHALL apply the same filters and grouping as the on-screen report and contain the same rows and values.

#### Scenario: Filtered export
- **WHEN** a user filters by cashier and exports
- **THEN** the CSV rows equal the filtered report rows

### Requirement: Export respects permissions
Exports SHALL require the same permission as the report and SHALL NOT include fields the user cannot view.

#### Scenario: Unauthorized export
- **WHEN** a cashier requests the profit export
- **THEN** the system responds with 403

### Requirement: Spreadsheet-friendly format
CSV files SHALL be UTF-8 with byte order mark, use comma separators, plain numeric amounts in VND without currency symbols, ISO dates, and a filename containing the report name and date range.

#### Scenario: Vietnamese names
- **WHEN** an export containing "Cà phê sữa đá" is opened in a spreadsheet application
- **THEN** the name displays correctly
