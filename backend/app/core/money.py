from decimal import ROUND_HALF_UP, Decimal

MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.0001")
UNIT_COST_QUANTUM = Decimal("0.0001")


def money(value: Decimal) -> Decimal:
    """Round to the Numeric(18, 2) money scale."""
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def quantity(value: Decimal) -> Decimal:
    """Round to the Numeric(18, 4) quantity scale."""
    return value.quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)


def unit_cost(value: Decimal) -> Decimal:
    """Round to the Numeric(18, 4) unit-cost scale."""
    return value.quantize(UNIT_COST_QUANTUM, rounding=ROUND_HALF_UP)


def optional_money(value: Decimal | None) -> Decimal | None:
    return None if value is None else money(value)
