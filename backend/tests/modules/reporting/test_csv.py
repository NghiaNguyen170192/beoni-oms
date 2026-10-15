from datetime import date
from decimal import Decimal

from app.modules.reporting.csv import plain, render_csv


def test_csv_is_utf8_bom_with_plain_numbers_and_iso_dates() -> None:
    payload = render_csv(
        ["name", "amount", "sold_on"],
        [["Cà phê sữa đá", Decimal("10200.00"), date(2026, 10, 15)]],
    )
    assert payload.startswith(b"\xef\xbb\xbf")
    text = payload.decode("utf-8-sig")
    assert "₫" not in text
    assert "Cà phê sữa đá" in text
    assert "10200.00" in text
    assert "2026-10-15" in text
    assert text.splitlines()[0] == "name,amount,sold_on"


def test_plain_decimal_keeps_scale() -> None:
    assert plain(Decimal("550000.00")) == "550000.00"
    assert plain(None) == ""
