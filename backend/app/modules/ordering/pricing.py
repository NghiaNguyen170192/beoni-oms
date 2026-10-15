"""Order math: pure Decimal functions, whole-VND rounding (ROUND_HALF_UP).

Prices are tax-inclusive. Subtotal is the sum of gross line amounts; discount
total is line discounts plus the order discount; total = subtotal - discounts.
The order discount is allocated to lines in proportion to their totals after
line discounts (the last line takes the rounding remainder), giving each line
a net amount for product reports.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

ZERO = Decimal("0")
HUNDRED = Decimal("100")
VND = Decimal("1")


class DiscountType(str, Enum):
    AMOUNT = "amount"
    PERCENT = "percent"


class PricingError(ValueError):
    pass


class InvalidDiscount(PricingError):
    pass


class DiscountExceedsBase(PricingError):
    pass


def round_vnd(value: Decimal) -> Decimal:
    return value.quantize(VND, rounding=ROUND_HALF_UP)


def discount_amount(
    base: Decimal, discount_type: DiscountType | None, value: Decimal | None
) -> Decimal:
    """Discount in VND for `base`; percentages are 0-100, amounts may not exceed base."""
    if discount_type is None:
        return ZERO
    if value is None or value < 0:
        raise InvalidDiscount("Discount must be zero or more")
    if discount_type == DiscountType.PERCENT:
        if value > HUNDRED:
            raise InvalidDiscount("Percentage discount must be between 0 and 100")
        return round_vnd(base * value / HUNDRED)
    amount = round_vnd(value)
    if amount > base:
        raise DiscountExceedsBase(
            f"Discount {amount} exceeds the amount it applies to ({base})"
        )
    return amount


def included_tax(amount: Decimal, rate: Decimal) -> Decimal:
    """Tax contained in a tax-inclusive `amount` at `rate` percent."""
    if rate <= 0:
        return ZERO
    return round_vnd(amount * rate / (HUNDRED + rate))


def allocate(amount: Decimal, bases: Sequence[Decimal]) -> list[Decimal]:
    """Split `amount` across `bases` proportionally in whole VND.

    The last line with a positive base takes the remainder so shares sum exactly.
    """
    total = sum(bases, ZERO)
    shares = [ZERO] * len(bases)
    if amount == 0 or total == 0:
        return shares
    last = max(i for i, base in enumerate(bases) if base > 0)
    allocated = ZERO
    for i, base in enumerate(bases):
        if i == last:
            shares[i] = amount - allocated
        elif base > 0:
            shares[i] = round_vnd(amount * base / total)
            allocated += shares[i]
    return shares


@dataclass(frozen=True)
class LineInput:
    unit_price: Decimal
    quantity: Decimal
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = None


@dataclass(frozen=True)
class LineAmounts:
    gross: Decimal
    discount_amount: Decimal
    line_total: Decimal
    order_discount_share: Decimal
    net_total: Decimal
    tax_amount: Decimal


@dataclass(frozen=True)
class OrderAmounts:
    lines: list[LineAmounts]
    subtotal: Decimal
    order_discount_amount: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal


def price_order(
    lines: Sequence[LineInput],
    *,
    order_discount_type: DiscountType | None = None,
    order_discount_value: Decimal | None = None,
    tax_rate: Decimal = ZERO,
) -> OrderAmounts:
    gross = [round_vnd(line.unit_price * line.quantity) for line in lines]
    line_discounts = [
        discount_amount(g, line.discount_type, line.discount_value)
        for g, line in zip(gross, lines, strict=True)
    ]
    line_totals = [g - d for g, d in zip(gross, line_discounts, strict=True)]
    after_line_discounts = sum(line_totals, ZERO)
    order_discount = discount_amount(
        after_line_discounts, order_discount_type, order_discount_value
    )
    shares = allocate(order_discount, line_totals)
    nets = [t - s for t, s in zip(line_totals, shares, strict=True)]
    taxes = [included_tax(n, tax_rate) for n in nets]

    subtotal = sum(gross, ZERO)
    discount_total = sum(line_discounts, ZERO) + order_discount
    return OrderAmounts(
        lines=[
            LineAmounts(
                gross=g,
                discount_amount=d,
                line_total=t,
                order_discount_share=s,
                net_total=n,
                tax_amount=x,
            )
            for g, d, t, s, n, x in zip(
                gross, line_discounts, line_totals, shares, nets, taxes, strict=True
            )
        ],
        subtotal=subtotal,
        order_discount_amount=order_discount,
        discount_total=discount_total,
        tax_total=sum(taxes, ZERO),
        total=subtotal - discount_total,
    )
