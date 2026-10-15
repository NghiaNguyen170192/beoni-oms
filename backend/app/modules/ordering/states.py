from enum import Enum

from app.core.errors import Conflict


class OrderStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PAID = "paid"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"


S = OrderStatus

# Transitions staff can request directly.
ALLOWED: dict[OrderStatus, frozenset[OrderStatus]] = {
    S.DRAFT: frozenset({S.CONFIRMED, S.CANCELLED, S.COMPLETED}),
    S.CONFIRMED: frozenset({S.CANCELLED, S.COMPLETED}),
    S.PAID: frozenset({S.COMPLETED}),
    S.COMPLETED: frozenset(),
    S.CANCELLED: frozenset(),
    S.PARTIALLY_REFUNDED: frozenset(),
    S.REFUNDED: frozenset(),
}

# Transitions reachable only through payment and refund operations.
PAYMENT_ALLOWED: dict[OrderStatus, frozenset[OrderStatus]] = {
    S.DRAFT: frozenset({S.PAID}),
    S.CONFIRMED: frozenset({S.PAID}),
    S.PAID: frozenset({S.PARTIALLY_REFUNDED, S.REFUNDED}),
    S.COMPLETED: frozenset({S.PARTIALLY_REFUNDED, S.REFUNDED}),
    S.PARTIALLY_REFUNDED: frozenset({S.PARTIALLY_REFUNDED, S.REFUNDED}),
    S.CANCELLED: frozenset(),
    S.REFUNDED: frozenset(),
}

OPEN_STATUSES = frozenset({S.DRAFT, S.CONFIRMED})


class InvalidTransition(Conflict):
    pass


def can_transition(
    current: OrderStatus, target: OrderStatus, *, via_payment: bool = False
) -> bool:
    table = PAYMENT_ALLOWED if via_payment else ALLOWED
    return target in table[current]


def assert_transition(
    current: OrderStatus, target: OrderStatus, *, via_payment: bool = False
) -> None:
    if not can_transition(current, target, via_payment=via_payment):
        raise InvalidTransition(
            f"Cannot change an order from {current.value} to {target.value}"
        )
