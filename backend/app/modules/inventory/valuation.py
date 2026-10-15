"""Weighted-average stock valuation. Pure Decimal math, no database access."""

from dataclasses import dataclass
from decimal import Decimal

from app.core.money import money, quantity, unit_cost

ZERO = Decimal("0")


def to_base_quantity(purchase_quantity: Decimal, conversion_factor: Decimal) -> Decimal:
    """Purchase-unit quantity in base units (5 kg at factor 1000 -> 5000 g)."""
    if conversion_factor <= 0:
        raise ValueError("Conversion factor must be positive")
    return quantity(purchase_quantity * conversion_factor)


@dataclass(frozen=True)
class MovementEffect:
    unit_cost: Decimal
    value: Decimal
    quantity_after: Decimal
    avg_cost_after: Decimal
    value_after: Decimal
    cost_uncertain: bool


def apply_movement(
    *,
    quantity_before: Decimal,
    avg_cost_before: Decimal,
    change: Decimal,
    incoming_cost: Decimal | None = None,
    remove_at_cost: Decimal | None = None,
) -> MovementEffect:
    """Effect of posting a signed `change` on a balance.

    Incoming stock is valued at `incoming_cost` (or the current average when
    none is given) and re-averages the balance; if the balance was zero or
    negative the new average is simply the incoming cost. Outgoing stock is
    valued at the current average, which it leaves unchanged, unless
    `remove_at_cost` is set (receipt reversal): that cost is removed and the
    average is recomputed. A movement is cost-uncertain when it is valued at
    an unknown (zero) average or touches a negative balance.
    """
    if change == 0:
        raise ValueError("Movement quantity must be non-zero")
    quantity_after = quantity(quantity_before + change)

    if change > 0:
        cost = avg_cost_before if incoming_cost is None else unit_cost(incoming_cost)
        if quantity_before <= 0:
            avg_after = cost
        else:
            total_value = quantity_before * avg_cost_before + change * cost
            avg_after = unit_cost(total_value / quantity_after)
        uncertain = (
            incoming_cost is None and avg_cost_before == 0
        ) or quantity_before < 0
    elif remove_at_cost is not None:
        cost = unit_cost(remove_at_cost)
        if quantity_after > 0:
            total_value = quantity_before * avg_cost_before + change * cost
            avg_after = (
                unit_cost(total_value / quantity_after)
                if total_value > 0
                else Decimal("0")
            )
        elif quantity_after == 0:
            avg_after = Decimal("0")
        else:
            avg_after = avg_cost_before
        uncertain = quantity_after < 0
    else:
        cost = avg_cost_before
        avg_after = avg_cost_before
        uncertain = avg_cost_before == 0 or quantity_after < 0

    return MovementEffect(
        unit_cost=cost,
        value=money(change * cost),
        quantity_after=quantity_after,
        avg_cost_after=avg_after,
        value_after=money(quantity_after * avg_after),
        cost_uncertain=uncertain,
    )
