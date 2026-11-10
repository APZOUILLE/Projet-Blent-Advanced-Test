"""SQLite persistence for implementation B.

Schema (two normalised tables):

    purchase_orders(id, customer_id, subtotal_cents, discount_cents,
                    shipping_cents, total_cents, placed_at)
    purchase_order_lines(order_id, sku, quantity, unit_price_cents)

Implementation A stores the very same orders in a single `orders` table with a
JSON blob. A test that runs `SELECT ... FROM orders` has picked a side.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime

from shop.errors import PersistenceUnavailable
from shop.ports import OrderLine, OrderRecord

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        subtotal_cents INTEGER NOT NULL,
        discount_cents INTEGER NOT NULL,
        shipping_cents INTEGER NOT NULL,
        total_cents INTEGER NOT NULL,
        placed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS purchase_order_lines (
        order_id TEXT NOT NULL,
        position INTEGER NOT NULL,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price_cents INTEGER NOT NULL
    )
    """,
)


class SqliteOrderRepository:
    """Store orders in SQLite. Accepts a file path or `":memory:"`."""

    def __init__(self, database: str = ":memory:") -> None:
        self.database = database
        self._connection = sqlite3.connect(database, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            for statement in _SCHEMA:
                self._connection.execute(statement)
            self._connection.commit()

    def save(self, order: OrderRecord) -> None:
        try:
            with self._lock:
                self._connection.execute(
                    "INSERT INTO purchase_orders (id, customer_id, subtotal_cents,"
                    " discount_cents, shipping_cents, total_cents, placed_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        order.order_id,
                        order.customer_id,
                        order.subtotal_cents,
                        order.discount_cents,
                        order.shipping_cents,
                        order.total_cents,
                        order.placed_at.isoformat(),
                    ),
                )
                self._connection.executemany(
                    "INSERT INTO purchase_order_lines (order_id, position, sku,"
                    " quantity, unit_price_cents) VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            order.order_id,
                            position,
                            line.sku,
                            line.quantity,
                            line.unit_price_cents,
                        )
                        for position, line in enumerate(order.lines)
                    ],
                )
                self._connection.commit()
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            raise PersistenceUnavailable(
                "The order store rejected the write: " + str(exc)
            ) from exc

    def get(self, order_id: str) -> OrderRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM purchase_orders WHERE id = ?", (order_id,)
            ).fetchone()
            if row is None:
                return None
            lines = self._lines_for(order_id)
        return _record(row, lines)

    def list_for_customer(self, customer_id: str) -> list[OrderRecord]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM purchase_orders WHERE customer_id = ? ORDER BY id",
                (customer_id,),
            ).fetchall()
            records = [(row, self._lines_for(row["id"])) for row in rows]
        return [_record(row, lines) for row, lines in records]

    def count_for_customer(self, customer_id: str) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS n FROM purchase_orders WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
        return int(row["n"])

    def _lines_for(self, order_id: str) -> tuple[OrderLine, ...]:
        rows = self._connection.execute(
            "SELECT sku, quantity, unit_price_cents FROM purchase_order_lines"
            " WHERE order_id = ? ORDER BY position",
            (order_id,),
        ).fetchall()
        return tuple(
            OrderLine(
                sku=row["sku"],
                quantity=row["quantity"],
                unit_price_cents=row["unit_price_cents"],
            )
            for row in rows
        )


def _record(row: sqlite3.Row, lines: tuple[OrderLine, ...]) -> OrderRecord:
    return OrderRecord(
        order_id=row["id"],
        customer_id=row["customer_id"],
        lines=lines,
        subtotal_cents=row["subtotal_cents"],
        discount_cents=row["discount_cents"],
        shipping_cents=row["shipping_cents"],
        total_cents=row["total_cents"],
        placed_at=datetime.fromisoformat(row["placed_at"]),
    )
