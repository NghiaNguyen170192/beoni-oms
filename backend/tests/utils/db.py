from typing import Any

from sqlalchemy import Engine


def purge_committed(engine: Engine, *statements: Any) -> None:
    """Delete rows committed by concurrency tests, including from append-only
    ledgers. `session_replication_role = replica` skips their guard triggers
    (and FK checks) for this transaction only; needs a superuser connection."""
    with engine.begin() as connection:
        connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
        for statement in statements:
            connection.execute(statement)
