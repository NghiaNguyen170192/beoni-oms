import pytest

from app.modules.ordering.states import (
    InvalidTransition,
    OrderStatus,
    assert_transition,
    can_transition,
)

S = OrderStatus

ALLOWED = [
    (S.DRAFT, S.CONFIRMED),
    (S.DRAFT, S.CANCELLED),
    (S.CONFIRMED, S.CANCELLED),
    (S.DRAFT, S.COMPLETED),
    (S.CONFIRMED, S.COMPLETED),
    (S.PAID, S.COMPLETED),
]

REJECTED = [
    (S.COMPLETED, S.CANCELLED),
    (S.COMPLETED, S.COMPLETED),
    (S.COMPLETED, S.DRAFT),
    (S.CANCELLED, S.CONFIRMED),
    (S.CANCELLED, S.COMPLETED),
    (S.CONFIRMED, S.DRAFT),
    (S.CONFIRMED, S.CONFIRMED),
    (S.PAID, S.CANCELLED),
    (S.REFUNDED, S.COMPLETED),
    # Payment-only targets are never reachable as plain transitions.
    (S.DRAFT, S.PAID),
    (S.CONFIRMED, S.PAID),
    (S.COMPLETED, S.REFUNDED),
    (S.COMPLETED, S.PARTIALLY_REFUNDED),
]


@pytest.mark.parametrize(("current", "target"), ALLOWED)
def test_allowed_transitions(current: OrderStatus, target: OrderStatus) -> None:
    assert_transition(current, target)


@pytest.mark.parametrize(("current", "target"), REJECTED)
def test_rejected_transitions(current: OrderStatus, target: OrderStatus) -> None:
    with pytest.raises(InvalidTransition) as exc_info:
        assert_transition(current, target)
    assert exc_info.value.status_code == 409


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.DRAFT, S.PAID),
        (S.CONFIRMED, S.PAID),
        (S.COMPLETED, S.PARTIALLY_REFUNDED),
        (S.COMPLETED, S.REFUNDED),
        (S.PARTIALLY_REFUNDED, S.REFUNDED),
    ],
)
def test_payment_transitions(current: OrderStatus, target: OrderStatus) -> None:
    assert can_transition(current, target, via_payment=True)


def test_payment_operations_cannot_complete_or_cancel() -> None:
    assert not can_transition(S.PAID, S.COMPLETED, via_payment=True)
    assert not can_transition(S.CANCELLED, S.PAID, via_payment=True)
    assert not can_transition(S.REFUNDED, S.REFUNDED, via_payment=True)
