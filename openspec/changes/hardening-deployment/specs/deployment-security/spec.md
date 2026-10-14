# Spec Delta

## Purpose

Defines the security properties a production deployment must have: encrypted transport, safe headers, restricted origins, secret handling, and no development-only routes.

## ADDED Requirements

### Requirement: HTTPS only in production
In production, the frontend and API SHALL be served only over HTTPS, and HTTP requests SHALL redirect to HTTPS.

#### Scenario: HTTP request
- **WHEN** a client requests the API over HTTP in production
- **THEN** it is redirected to the HTTPS URL

### Requirement: Secure response headers
Production responses SHALL include Strict-Transport-Security, X-Content-Type-Options nosniff, a restrictive Referrer-Policy, and frame protection.

#### Scenario: Header check
- **WHEN** any production API response is inspected
- **THEN** the required headers are present

### Requirement: Restricted CORS
In production, the API SHALL accept cross-origin requests only from the configured frontend origin.

#### Scenario: Foreign origin
- **WHEN** a browser on another origin calls the API
- **THEN** the CORS preflight is rejected

### Requirement: Production configuration guard
The application SHALL refuse to start in production when the secret key, database password, or first superuser password is a default or placeholder value.

#### Scenario: Default secret
- **WHEN** the application starts in production with SECRET_KEY "changethis"
- **THEN** startup fails with a configuration error

### Requirement: No development routes in production
Development-only routes (private user creation, test email, API docs if disabled by configuration) SHALL NOT be reachable in production.

#### Scenario: Private route
- **WHEN** a client calls the private user-creation route in production
- **THEN** the system responds with 404

### Requirement: Every route declares its access
Every API route SHALL be either explicitly public or protected by a permission check, verified by an automated test enumerating all routes.

#### Scenario: Unprotected route added
- **WHEN** a developer adds a route without a permission dependency or public marker
- **THEN** the route-access test fails
