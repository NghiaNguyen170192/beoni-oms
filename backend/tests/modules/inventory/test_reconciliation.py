"""Database-wide ledger checks; they also cover data left by end-to-end runs."""

from sqlalchemy import text
from sqlmodel import Session


def test_every_balance_equals_sum_of_movements(db: Session) -> None:
    mismatches = db.connection().execute(
        text(
            """
            SELECT b.item_id, b.quantity, COALESCE(SUM(m.quantity), 0) AS ledger
            FROM inventory_balances b
            LEFT JOIN inventory_movements m ON m.item_id = b.item_id
            GROUP BY b.item_id, b.quantity
            HAVING b.quantity <> COALESCE(SUM(m.quantity), 0)
            """
        )
    )
    assert mismatches.all() == []


def test_every_item_has_a_balance_row(db: Session) -> None:
    missing = db.connection().execute(
        text(
            """
            SELECT i.id FROM inventory_items i
            LEFT JOIN inventory_balances b ON b.item_id = i.id
            WHERE b.item_id IS NULL
            """
        )
    )
    assert missing.all() == []


def test_latest_running_balance_matches_balance(db: Session) -> None:
    mismatches = db.connection().execute(
        text(
            """
            SELECT DISTINCT ON (m.item_id) m.item_id, m.quantity_after, b.quantity
            FROM inventory_movements m
            JOIN inventory_balances b ON b.item_id = m.item_id
            ORDER BY m.item_id, m.seq DESC
            """
        )
    )
    assert [row for row in mismatches if row.quantity_after != row.quantity] == []
