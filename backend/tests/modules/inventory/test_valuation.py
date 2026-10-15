from decimal import Decimal

import pytest

from app.modules.inventory.valuation import apply_movement, to_base_quantity

D = Decimal


def test_purchase_quantity_converted_to_base_units() -> None:
    assert to_base_quantity(D("5"), D("1000")) == D("5000")
    assert to_base_quantity(D("0.25"), D("1000")) == D("250")


@pytest.mark.parametrize("factor", [D("0"), D("-1")])
def test_invalid_conversion_factor_rejected(factor: Decimal) -> None:
    with pytest.raises(ValueError):
        to_base_quantity(D("1"), factor)


def test_receive_at_different_cost_reaverages() -> None:
    effect = apply_movement(
        quantity_before=D("1000"),
        avg_cost_before=D("0.5"),
        change=D("1000"),
        incoming_cost=D("0.7"),
    )
    assert effect.quantity_after == D("2000")
    assert effect.avg_cost_after == D("0.6")
    assert effect.unit_cost == D("0.7")
    assert effect.value == D("700")
    assert effect.value_after == D("1200")
    assert effect.cost_uncertain is False


def test_receipt_into_empty_stock_takes_incoming_cost() -> None:
    effect = apply_movement(
        quantity_before=D("0"),
        avg_cost_before=D("0"),
        change=D("500"),
        incoming_cost=D("1.2"),
    )
    assert effect.avg_cost_after == D("1.2")
    assert effect.cost_uncertain is False


def test_receipt_into_negative_stock_does_not_average_with_negative_balance() -> None:
    effect = apply_movement(
        quantity_before=D("-100"),
        avg_cost_before=D("0.5"),
        change=D("1000"),
        incoming_cost=D("0.8"),
    )
    assert effect.quantity_after == D("900")
    assert effect.avg_cost_after == D("0.8")
    assert effect.cost_uncertain is True


def test_removing_a_receipt_at_its_cost_restores_the_previous_average() -> None:
    effect = apply_movement(
        quantity_before=D("5000"),
        avg_cost_before=D("400"),
        change=D("-5000"),
        remove_at_cost=D("400"),
    )
    assert effect.unit_cost == D("400")
    assert effect.value == D("-2000000.00")
    assert effect.quantity_after == D("0")
    assert effect.avg_cost_after == D("0")


def test_outgoing_uses_current_average_and_keeps_it() -> None:
    effect = apply_movement(
        quantity_before=D("2000"), avg_cost_before=D("0.6"), change=D("-18")
    )
    assert effect.unit_cost == D("0.6")
    assert effect.value == D("-10.80")
    assert effect.avg_cost_after == D("0.6")
    assert effect.quantity_after == D("1982")
    assert effect.cost_uncertain is False


def test_outgoing_with_unknown_cost_is_uncertain() -> None:
    effect = apply_movement(
        quantity_before=D("100"), avg_cost_before=D("0"), change=D("-10")
    )
    assert effect.cost_uncertain is True


def test_outgoing_into_negative_is_uncertain() -> None:
    effect = apply_movement(
        quantity_before=D("5"), avg_cost_before=D("1"), change=D("-10")
    )
    assert effect.quantity_after == D("-5")
    assert effect.cost_uncertain is True


def test_increase_without_cost_keeps_average() -> None:
    effect = apply_movement(
        quantity_before=D("1900"), avg_cost_before=D("0.6"), change=D("100")
    )
    assert effect.unit_cost == D("0.6")
    assert effect.avg_cost_after == D("0.6")
    assert effect.cost_uncertain is False


def test_average_rounded_to_four_places() -> None:
    effect = apply_movement(
        quantity_before=D("3"),
        avg_cost_before=D("1"),
        change=D("3"),
        incoming_cost=D("2.0001"),
    )
    assert effect.avg_cost_after == D("1.5001")


def test_zero_change_rejected() -> None:
    with pytest.raises(ValueError):
        apply_movement(quantity_before=D("1"), avg_cost_before=D("1"), change=D("0"))
