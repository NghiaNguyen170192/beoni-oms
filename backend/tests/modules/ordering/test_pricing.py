from decimal import Decimal

import pytest

from app.modules.ordering.pricing import (
    DiscountExceedsBase,
    DiscountType,
    InvalidDiscount,
    LineInput,
    allocate,
    discount_amount,
    included_tax,
    price_order,
    round_vnd,
)

D = Decimal
P = DiscountType.PERCENT
A = DiscountType.AMOUNT


def test_line_total_is_price_times_quantity() -> None:
    result = price_order([LineInput(unit_price=D("29000"), quantity=D("2"))])
    assert result.lines[0].line_total == D("58000")
    assert result.subtotal == result.total == D("58000")


def test_spec_example_order_discount_ten_percent() -> None:
    result = price_order(
        [
            LineInput(unit_price=D("29000"), quantity=D("2")),
            LineInput(unit_price=D("35000"), quantity=D("1")),
        ],
        order_discount_type=P,
        order_discount_value=D("10"),
    )
    assert result.subtotal == D("93000")
    assert result.discount_total == D("9300")
    assert result.total == D("83700")
    assert [line.order_discount_share for line in result.lines] == [
        D("5800"),
        D("3500"),
    ]
    assert [line.net_total for line in result.lines] == [D("52200"), D("31500")]


def test_fractional_quantity_rounds_to_whole_vnd() -> None:
    result = price_order([LineInput(unit_price=D("25000"), quantity=D("0.333"))])
    assert result.lines[0].gross == D("8325")
    result = price_order([LineInput(unit_price=D("15500"), quantity=D("1.5"))])
    assert result.lines[0].gross == D("23250")


def test_line_discounts_amount_and_percent() -> None:
    result = price_order(
        [
            LineInput(
                unit_price=D("30000"),
                quantity=D("1"),
                discount_type=A,
                discount_value=D("5000"),
            ),
            LineInput(
                unit_price=D("45000"),
                quantity=D("1"),
                discount_type=P,
                discount_value=D("20"),
            ),
        ]
    )
    assert [line.discount_amount for line in result.lines] == [D("5000"), D("9000")]
    assert result.subtotal == D("75000")
    assert result.discount_total == D("14000")
    assert result.total == D("61000")


def test_order_discount_applies_after_line_discounts() -> None:
    result = price_order(
        [
            LineInput(
                unit_price=D("100000"),
                quantity=D("1"),
                discount_type=A,
                discount_value=D("20000"),
            )
        ],
        order_discount_type=P,
        order_discount_value=D("50"),
    )
    assert result.order_discount_amount == D("40000")
    assert result.total == D("40000")


def test_allocation_remainder_goes_to_last_line() -> None:
    assert allocate(D("100"), [D("1"), D("1"), D("1")]) == [D("33"), D("33"), D("34")]
    assert sum(allocate(D("1001"), [D("333"), D("333"), D("334")])) == D("1001")


def test_allocation_skips_zero_lines() -> None:
    assert allocate(D("10"), [D("50"), D("0")]) == [D("10"), D("0")]
    assert allocate(D("0"), [D("50"), D("50")]) == [D("0"), D("0")]


def test_tax_inclusive() -> None:
    assert included_tax(D("108000"), D("8")) == D("8000")
    assert included_tax(D("50000"), D("0")) == D("0")
    result = price_order(
        [LineInput(unit_price=D("54000"), quantity=D("2"))], tax_rate=D("8")
    )
    assert result.total == D("108000")
    assert result.tax_total == D("8000")


def test_tax_follows_order_discount() -> None:
    result = price_order(
        [LineInput(unit_price=D("108000"), quantity=D("1"))],
        order_discount_type=P,
        order_discount_value=D("50"),
        tax_rate=D("8"),
    )
    assert result.total == D("54000")
    assert result.tax_total == D("4000")


def test_discount_exceeding_base_rejected() -> None:
    with pytest.raises(DiscountExceedsBase):
        price_order(
            [
                LineInput(
                    unit_price=D("30000"),
                    quantity=D("1"),
                    discount_type=A,
                    discount_value=D("50000"),
                )
            ]
        )
    with pytest.raises(DiscountExceedsBase):
        price_order(
            [LineInput(unit_price=D("30000"), quantity=D("1"))],
            order_discount_type=A,
            order_discount_value=D("30001"),
        )


@pytest.mark.parametrize(
    ("kind", "value"), [(P, D("101")), (P, D("-1")), (A, D("-1")), (A, None)]
)
def test_invalid_discount_values(kind: DiscountType, value: Decimal | None) -> None:
    with pytest.raises(InvalidDiscount):
        discount_amount(D("1000"), kind, value)


def test_full_discount_allowed() -> None:
    assert discount_amount(D("30000"), A, D("30000")) == D("30000")
    assert discount_amount(D("30000"), P, D("100")) == D("30000")


def test_round_half_up() -> None:
    assert round_vnd(D("0.5")) == D("1")
    assert round_vnd(D("2.5")) == D("3")
    assert round_vnd(D("2.4999")) == D("2")


def test_empty_order() -> None:
    result = price_order([])
    assert result.total == result.subtotal == D("0")
