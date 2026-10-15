"""Pure sale-consumption math. No database access."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.core.money import money, quantity

NON_STOCK = "non_stock"


@dataclass(frozen=True)
class Component:
    inventory_item_id: UUID
    quantity_per_serving: Decimal


@dataclass(frozen=True)
class ConsumptionLine:
    order_line_id: UUID
    quantity: Decimal
    product_type: str
    recipe_id: UUID | None
    components: tuple[Component, ...]


@dataclass(frozen=True)
class LineUsage:
    order_line_id: UUID
    recipe_id: UUID | None
    quantities: dict[UUID, Decimal]


@dataclass(frozen=True)
class Requirements:
    by_item: dict[UUID, Decimal]
    by_line: tuple[LineUsage, ...]


def aggregate_requirements(lines: list[ConsumptionLine]) -> Requirements:
    """Sum stock per inventory item, and keep each order line's own usage.

    Non-stock lines contribute nothing. Component quantities are rounded to the
    stock scale before they are added, so shared ingredients stay exact.
    """
    by_item: dict[UUID, Decimal] = {}
    usages: list[LineUsage] = []
    for line in lines:
        if line.product_type == NON_STOCK:
            usages.append(LineUsage(line.order_line_id, None, {}))
            continue
        quantities: dict[UUID, Decimal] = {}
        for component in line.components:
            used = quantity(line.quantity * component.quantity_per_serving)
            if used == 0:
                continue
            current = quantities.get(component.inventory_item_id, Decimal("0"))
            quantities[component.inventory_item_id] = current + used
        for item_id, used in quantities.items():
            by_item[item_id] = by_item.get(item_id, Decimal("0")) + used
        usages.append(LineUsage(line.order_line_id, line.recipe_id, quantities))
    return Requirements(
        {item_id: quantity(total) for item_id, total in by_item.items()},
        tuple(usages),
    )


@dataclass(frozen=True)
class Allocation:
    order_line_id: UUID
    quantity: Decimal
    value: Decimal


def allocate_movement(
    *, movement_quantity: Decimal, movement_value: Decimal, parts: dict[UUID, Decimal]
) -> list[Allocation]:
    """Split a movement across lines in proportion to positive `parts`.

    The last line (by id) absorbs the rounding remainder, so the allocations
    sum to the movement's quantity and value.
    """
    if not parts:
        return []
    total_qty = sum(parts.values(), Decimal("0"))
    if total_qty == 0:
        raise ValueError("Cannot allocate a movement with zero quantity")
    ordered = sorted(parts)
    remaining_qty = movement_quantity
    remaining_value = movement_value
    result: list[Allocation] = []
    for index, line_id in enumerate(ordered):
        if index == len(ordered) - 1:
            share_qty = remaining_qty
            share_value = remaining_value
        else:
            weight = parts[line_id] / total_qty
            share_qty = quantity(movement_quantity * weight)
            share_value = money(movement_value * weight)
            remaining_qty -= share_qty
            remaining_value -= share_value
        if share_qty == 0 and share_value == 0:
            continue
        result.append(Allocation(line_id, share_qty, share_value))
    return result
