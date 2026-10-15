import json
import logging
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlmodel import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.logging import REQUEST_ID_HEADER, JsonFormatter
from app.main import app

API = settings.API_V1_STR


def _request_records(
    caplog: pytest.LogCaptureFixture, message: str
) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage() == message]


def test_generated_request_id_is_returned_and_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    r = client.get(f"{API}/utils/health-check/")

    request_id = r.headers[REQUEST_ID_HEADER]
    assert request_id
    records = _request_records(caplog, "Request completed")
    assert records
    assert records[-1].request_id == request_id  # type: ignore[attr-defined]


def test_client_request_id_is_propagated(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    r = client.get(f"{API}/utils/health-check/", headers={REQUEST_ID_HEADER: "abc-123"})

    assert r.headers[REQUEST_ID_HEADER] == "abc-123"
    assert _request_records(caplog, "Request completed")[-1].request_id == "abc-123"  # type: ignore[attr-defined]


def test_malformed_request_id_is_replaced(client: TestClient) -> None:
    r = client.get(
        f"{API}/utils/health-check/", headers={REQUEST_ID_HEADER: "bad id with spaces"}
    )

    assert r.headers[REQUEST_ID_HEADER] != "bad id with spaces"


def test_json_formatter_emits_structured_line(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    r = client.get(f"{API}/utils/health-check/")
    record = _request_records(caplog, "Request completed")[-1]

    line = json.loads(JsonFormatter().format(record))

    assert line["request_id"] == r.headers[REQUEST_ID_HEADER]
    assert line["level"] == "INFO"
    assert line["message"] == "Request completed"
    assert line["timestamp"]
    assert line["status_code"] == 200


def test_login_failure_log_does_not_contain_password(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    password = "Sup3r-Secret-Passw0rd"
    r = client.post(
        f"{API}/login/access-token",
        data={"username": settings.FIRST_SUPERUSER, "password": password},
    )

    assert r.status_code == 400
    assert _request_records(caplog, "Login failed: incorrect email or password")
    formatter = JsonFormatter()
    for record in caplog.records:
        assert password not in formatter.format(record)


def test_readiness_ok(client: TestClient) -> None:
    r = client.get(f"{API}/utils/ready/")

    assert r.status_code == 200
    assert r.json() is True


def test_readiness_reports_database_down_while_liveness_succeeds(
    client: TestClient,
) -> None:
    unreachable = create_engine(
        "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none",
        connect_args={"connect_timeout": 1},
    )

    def broken_db() -> Generator[Session, None, None]:
        with Session(unreachable) as session:
            yield session

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = broken_db
    try:
        ready = client.get(f"{API}/utils/ready/")
        live = client.get(f"{API}/utils/health-check/")
    finally:
        if previous is not None:
            app.dependency_overrides[get_db] = previous
        unreachable.dispose()

    assert ready.status_code == 503
    assert ready.json() == {"detail": "Database unavailable"}
    assert live.status_code == 200


@pytest.fixture()
def failing_route() -> Generator[str, None, None]:
    path = "/__test__/boom"

    def boom() -> None:
        raise RuntimeError("secret internal detail")

    app.add_api_route(path, boom, methods=["GET"], tags=["test"])
    try:
        yield path
    finally:
        app.router.routes[:] = [
            route for route in app.router.routes if getattr(route, "path", None) != path
        ]


def test_unhandled_error_returns_generic_500_and_logs_request_id(
    client: TestClient, failing_route: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    r = client.get(failing_route)

    request_id = r.headers[REQUEST_ID_HEADER]
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error", "request_id": request_id}
    assert "secret internal detail" not in r.text
    assert "Traceback" not in r.text

    errors = _request_records(caplog, "Unhandled error")
    assert len(errors) == 1
    assert errors[0].request_id == request_id  # type: ignore[attr-defined]
    assert "secret internal detail" in JsonFormatter().format(errors[0])
