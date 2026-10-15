from datetime import date

from fastapi.testclient import TestClient

from app.core.config import settings
from app.modules.identity.roles import Role

API = settings.API_V1_STR


def test_cashier_dashboard_omits_cost_and_profit(
    client: TestClient, role_token_headers
) -> None:
    cashier = role_token_headers(Role.CASHIER)
    today = date.today().isoformat()
    response = client.get(
        f"{API}/reports/dashboard",
        headers=cashier,
        params={"date_from": today, "date_to": today},
    )
    assert response.status_code == 200
    body = response.json()
    assert "net_sales" in body
    assert "low_stock_count" in body
    assert "cogs" not in body
    assert "gross_profit" not in body
    assert "operating_profit" not in body


def test_inventory_staff_cannot_read_profit(
    client: TestClient, role_token_headers
) -> None:
    staff = role_token_headers(Role.INVENTORY_STAFF)
    today = date.today().isoformat()
    response = client.get(
        f"{API}/reports/profit/statement",
        headers=staff,
        params={"date_from": today, "date_to": today},
    )
    assert response.status_code == 403
    export = client.get(
        f"{API}/reports/profit/statement.csv",
        headers=staff,
        params={"date_from": today, "date_to": today},
    )
    assert export.status_code == 403
