# Spec Delta

## Purpose

Provides shop owners with persistent, actionable in-app notifications for completed POS orders, including read/unread tracking and visible alerts while signed in.

## ADDED Requirements

### Requirement: Notify owners when a POS order is completed
The system SHALL create one unread in-app notification for each active owner when a POS order successfully transitions to completed.

#### Scenario: Completed POS order
- **WHEN** a cashier successfully completes a POS order
- **THEN** each active owner receives one unread notification identifying the order

#### Scenario: Completion retried
- **WHEN** the same order completion is retried
- **THEN** the system does not create duplicate notifications for that order

#### Scenario: Completion fails
- **WHEN** an order completion fails before the order reaches completed
- **THEN** the system does not create an order-completion notification

### Requirement: Restrict order notifications to owners
Only users with the existing owner role SHALL view order notifications; superusers treated as owners SHALL have the same access.

#### Scenario: Owner views notifications
- **WHEN** an active owner requests their notification center
- **THEN** the system returns only notifications belonging to that owner

#### Scenario: Non-owner requests notifications
- **WHEN** a user without the owner role requests order notifications
- **THEN** the system rejects the request without revealing notification data

### Requirement: Owners can review notification history
The system SHALL provide owners with a paginated notification center that distinguishes read from unread notifications and reports the unread count.

#### Scenario: Owner reviews notifications
- **WHEN** an owner opens the notification center
- **THEN** the system shows their notifications newest first, their read states, and the current unread count

### Requirement: Owners can change notification read state
The system SHALL let an owner mark their own notification as read or unread, and opening a notification SHALL mark it read.

#### Scenario: Owner opens an unread notification
- **WHEN** an owner opens an unread order notification
- **THEN** the notification becomes read and the unread count decreases

#### Scenario: Owner marks a notification unread
- **WHEN** an owner marks one of their read notifications unread
- **THEN** it appears as unread and contributes to the unread count

### Requirement: Show new notifications in a corner popup
While an owner is signed in, the application SHALL show a non-modal corner popup when a new unread order notification is available; dismissing the popup SHALL NOT mark the notification read.

#### Scenario: New unread order notification
- **WHEN** an order notification becomes available while the owner is signed in
- **THEN** the application shows a corner popup identifying the order

#### Scenario: Owner dismisses the popup
- **WHEN** an owner dismisses the corner popup without opening the notification
- **THEN** the notification remains unread in the notification center

### Requirement: Order notifications open the related order
The system SHALL let an owner open an order notification and navigate to the corresponding order details.

#### Scenario: Owner opens an order notification
- **WHEN** an owner opens an order notification from the center or corner popup
- **THEN** the notification is marked read and the corresponding order details open
