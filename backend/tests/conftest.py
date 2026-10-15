from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlmodel import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.modules.identity.roles import Role
from tests.utils.user import authentication_token_from_email, create_user_with_role
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def _initial_data() -> None:
    # Committed for real: the first superuser must exist for login-based fixtures.
    with Session(engine) as session:
        init_db(session)


CODE_SEQUENCES = ("menu_item_code_seq", "inventory_item_sku_seq")


@pytest.fixture(scope="session", autouse=True)
def _restore_code_sequences() -> Generator[None, None, None]:
    """Sequences ignore rollbacks; rewind them so test runs leave no gaps in
    the codes the local database hands out next."""
    with engine.connect() as connection:
        saved = {
            name: connection.execute(
                text(f"SELECT last_value, is_called FROM {name}")
            ).one()
            for name in CODE_SEQUENCES
        }
    yield
    with engine.begin() as connection:
        for name, (last_value, is_called) in saved.items():
            connection.execute(
                text("SELECT setval(:name, :value, :called)"),
                {"name": name, "value": last_value, "called": is_called},
            )


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Session inside an outer transaction that is rolled back after the test.

    `session.commit()` in code under test only releases a savepoint, so nothing
    a test writes is visible to other connections or survives the test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def db_engine() -> Engine:
    """Real engine for concurrency tests, which need independent committed
    transactions. Such tests must delete the rows they create."""
    return engine


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture()
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


@pytest.fixture()
def role_token_headers(
    client: TestClient, db: Session
) -> Callable[[Role], dict[str, str]]:
    """Factory: auth headers for a fresh user with the given role."""

    def make(role: Role) -> dict[str, str]:
        _, headers = create_user_with_role(client=client, db=db, role=role)
        return headers

    return make
