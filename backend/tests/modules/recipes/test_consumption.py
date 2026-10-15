import uuid
from decimal import Decimal

from app.modules.recipes.consumption import (
    Component,
    ConsumptionLine,
    aggregate_requirements,
    allocate_movement,
)

D = Decimal


def _line(
    qty: str,
    *components: tuple[uuid.UUID, str],
    product_type: str = "prepared",
    recipe_id: uuid.UUID | None = None,
) -> ConsumptionLine:
    return ConsumptionLine(
        order_line_id=uuid.uuid4(),
        quantity=D(qty),
        product_type=product_type,
        recipe_id=recipe_id,
        components=tuple(Component(item_id, D(per)) for item_id, per in components),
    )


def test_shared_ingredient_is_one_requirement() -> None:
    beans = uuid.uuid4()
    iced = _line("2", (beans, "18"))
    hot = _line("1", (beans, "20"))

    result = aggregate_requirements([iced, hot])

    assert result.by_item == {beans: D("56.0000")}
    by_line = {usage.order_line_id: usage.quantities for usage in result.by_line}
    assert by_line[iced.order_line_id] == {beans: D("36.0000")}
    assert by_line[hot.order_line_id] == {beans: D("20.0000")}


def test_non_stock_lines_consume_nothing() -> None:
    beans = uuid.uuid4()
    drink = _line("2", (beans, "18"))
    bag = _line("3", (beans, "500"), product_type="non_stock")

    result = aggregate_requirements([drink, bag])

    assert result.by_item == {beans: D("36.0000")}
    bag_usage = next(
        usage for usage in result.by_line if usage.order_line_id == bag.order_line_id
    )
    assert bag_usage.quantities == {}
    assert bag_usage.recipe_id is None


def test_fractional_quantities_round_to_stock_scale() -> None:
    syrup = uuid.uuid4()
    line = _line("1.5", (syrup, "0.3333"))

    result = aggregate_requirements([line])

    # 1.5 * 0.3333 = 0.49995, half-up to 4 decimal places.
    assert result.by_item == {syrup: D("0.5000")}


def test_allocations_sum_to_the_movement() -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    shares = allocate_movement(
        movement_quantity=D("-56.0000"),
        movement_value=D("-22400.00"),
        parts={first: D("36.0000"), second: D("20.0000")},
    )

    assert sum(share.quantity for share in shares) == D("-56.0000")
    assert sum(share.value for share in shares) == D("-22400.00")
    assert {share.order_line_id for share in shares} == {first, second}
