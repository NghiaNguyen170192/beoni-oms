# Spec Delta

## Purpose

Makes the running system diagnosable through correlated structured logs and health endpoints that report application and database status.

## ADDED Requirements

### Requirement: Every request has a correlation ID
The system SHALL accept an incoming `X-Request-ID` header or generate one, include it in every log line for that request, and return it in the response `X-Request-ID` header.

#### Scenario: Generated ID returned
- **WHEN** a request arrives without X-Request-ID
- **THEN** the response contains a generated X-Request-ID and log lines for the request include the same value

#### Scenario: Client ID propagated
- **WHEN** a request arrives with X-Request-ID "abc-123"
- **THEN** the response X-Request-ID is "abc-123"

### Requirement: Structured logs without secrets
Application logs SHALL be structured JSON lines with timestamp, level, message, and request ID, and SHALL NOT contain passwords, tokens, or secret settings.

#### Scenario: Login failure logged safely
- **WHEN** a login attempt fails
- **THEN** the log entry does not contain the submitted password

### Requirement: Liveness and readiness checks
The system SHALL expose an unauthenticated liveness check that succeeds when the process is running and a readiness check that succeeds only when the database is reachable.

#### Scenario: Database down
- **WHEN** the database is unreachable
- **THEN** the readiness check responds with 503 while the liveness check still succeeds

### Requirement: Unhandled errors are tracked
Unhandled server errors SHALL be logged with the request ID and reported to the configured error tracker when one is configured, and the client SHALL receive a generic 500 response without internal details.

#### Scenario: Unexpected exception
- **WHEN** a route raises an unexpected exception
- **THEN** the client receives a 500 with no stack trace and the log contains the error and request ID
