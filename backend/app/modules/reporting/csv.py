import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal

from fastapi.responses import StreamingResponse


def plain(value: object) -> str:
    """Spreadsheet cell: ISO dates and plain decimals, never a currency symbol."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_csv(header: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow([plain(cell) for cell in row])
    return buffer.getvalue().encode("utf-8-sig")


def csv_response(
    name: str,
    date_from: date,
    date_to: date,
    header: Sequence[str],
    rows: Iterable[Sequence[object]],
) -> StreamingResponse:
    filename = f"{name}_{date_from.isoformat()}_{date_to.isoformat()}.csv"
    payload = render_csv(header, rows)
    return StreamingResponse(
        iter([payload]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
