import uuid
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.main import app
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.dependencies import (
    IDEMPOTENCY_KEY_HEADER,
    IdempotencyKeyDep,
)

PATH = "/__test__/payments"


class PaymentIn(BaseModel):
    amount: Decimal


@pytest.fixture()
def calls() -> Generator[list[str], None, None]:
    performed: list[str] = []

    def record_payment(
        payment: PaymentIn, session: SessionDep, key: IdempotencyKeyDep
    ) -> JSONResponse:
        def operation() -> tuple[int, dict[str, object]]:
            payment_id = str(uuid.uuid4())
            performed.append(payment_id)
            return 201, {"id": payment_id, "amount": payment.amount}

        result = idempotency.execute(
            session,
            scope="test.payment",
            key=key,
            payload=payment.model_dump(mode="json"),
            operation=operation,
        )
        return JSONResponse(result.body, status_code=result.status_code)

    app.add_api_route(PATH, record_payment, methods=["POST"], tags=["test"])
    try:
        yield performed
    finally:
        app.router.routes[:] = [
            r for r in app.router.routes if getattr(r, "path", None) != PATH
        ]


def test_missing_key_returns_400_and_does_nothing(
    client: TestClient, calls: list[str]
) -> None:
    r = client.post(PATH, json={"amount": "45000"})

    assert r.status_code == 400
    assert r.json()["detail"] == "Idempotency-Key header is required"
    assert calls == []


def test_blank_key_returns_400(client: TestClient, calls: list[str]) -> None:
    r = client.post(PATH, json={"amount": "1"}, headers={IDEMPOTENCY_KEY_HEADER: " "})

    assert r.status_code == 400
    assert calls == []


def test_retried_request_returns_original_result(
    client: TestClient, calls: list[str]
) -> None:
    headers = {IDEMPOTENCY_KEY_HEADER: str(uuid.uuid4())}

    first = client.post(PATH, json={"amount": "45000"}, headers=headers)
    second = client.post(PATH, json={"amount": "45000"}, headers=headers)

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert first.json()["amount"] == "45000"
    assert len(calls) == 1


def test_same_key_different_payload_returns_422(
    client: TestClient, calls: list[str]
) -> None:
    headers = {IDEMPOTENCY_KEY_HEADER: str(uuid.uuid4())}
    client.post(PATH, json={"amount": "45000"}, headers=headers)

    r = client.post(PATH, json={"amount": "50000"}, headers=headers)

    assert r.status_code == 422
    assert len(calls) == 1
