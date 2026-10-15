import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.accounting.ledger import BANK, account_named
from app.modules.accounting.models import ExpenseCategory
from app.modules.identity.roles import Role

API = settings.API_V1_STR


def _key(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": uuid.uuid4().hex}


def test_cashier_cannot_read_cash_or_record_expenses(
    client: TestClient, role_token_headers
) -> None:
    cashier = role_token_headers(Role.CASHIER)
    assert client.get(f"{API}/cash/accounts", headers=cashier).status_code == 403
    assert client.post(f"{API}/expenses", headers=_key(cashier), json={}).status_code == 403


def test_manager_sees_recorded_balances_and_not_profit(
    client: TestClient, db: Session, role_token_headers
) -> None:
    manager = role_token_headers(Role.MANAGER)
    accounts = client.get(f"{API}/cash/accounts", headers=manager)
    assert accounts.status_code == 200
    body = accounts.json()
    assert body["count"] >= 2
    assert all(row["label"] == "recorded" for row in body["data"])
    cash = next(row for row in body["data"] if row["name"] == "Cash drawer")
    today = date.today().isoformat()
    movements = client.get(
        f"{API}/cash/movements",
        headers=manager,
        params={"account_id": cash["id"], "date_from": today, "date_to": today},
    )
    assert movements.status_code == 200
    report = movements.json()
    assert (
        Decimal(report["opening"]) + Decimal(report["inflows"]) - Decimal(report["outflows"])
        == Decimal(report["closing"])
    )
    summary = client.get(
        f"{API}/finance/summary",
        headers=manager,
        params={"date_from": today, "date_to": today},
    )
    assert summary.status_code == 403
    accountant = role_token_headers(Role.ACCOUNTANT)
    assert (
        client.get(
            f"{API}/finance/summary",
            headers=accountant,
            params={"date_from": today, "date_to": today},
        ).status_code
        == 200
    )
    rent = db.exec(select(ExpenseCategory).where(ExpenseCategory.name == "Rent")).one()
    bank = account_named(db, BANK)
    created = client.post(
        f"{API}/expenses",
        headers=_key(accountant),
        json={
            "category_id": str(rent.id),
            "amount": "1500000",
            "expense_date": today,
            "description": "Rent top-up",
            "payment_status": "paid",
            "account_id": str(bank.id),
        },
    )
    assert created.status_code == 201
    listed = client.get(
        f"{API}/expenses",
        headers=accountant,
        params={"category_id": str(rent.id), "date_from": today, "date_to": today},
    )
    assert listed.status_code == 200
    assert any(row["description"] == "Rent top-up" for row in listed.json()["data"])
