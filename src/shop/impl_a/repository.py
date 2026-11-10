"""SQLite persistence for implementation A.

Schema (one table, lines kept as JSON):

    orders(id, customer, total, ts, lines_json)

Implementation B uses a completely different schema. Both satisfy
`shop.ports.OrderRepository`, which is the only thing the HTTP contract knows
about.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime

from shop.errors import PersistenceUnavailable
from shop.ports import OrderLine, OrderRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    customer TEXT NOT NULL,
    total INTEGER NOT NULL,
    ts TEXT NOT NULL,
    lines_json TEXT NOT NULL
)
"""


class SqliteOrderRepository:
    """Store orders in SQLite. Accepts a file path or `":memory:"`."""

    def __init__(self, database: str = ":memory:") -> None:
        self.database = database
        # check_same_thread=False: TestClient runs synchronous routes in a
        # worker thread, so the connection is used from a thread other than the
        # one that created it. The lock keeps that safe.
        self._connection = sqlite3.connect(database, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._connection.execute(_SCHEMA)
            self._connection.commit()

    def save(self, order: OrderRecord) -> None:
        payload = {
            "lines": [
                {
                    "sku": line.sku,
                    "quantity": line.quantity,
                    "unit_price_cents": line.unit_price_cents,
                }
                for line in order.lines
            ],
            "discount_cents": order.discount_cents,
            "shipping_cents": order.shipping_cents,
        }
        try:
            with self._lock:
                self._connection.execute(
                    "INSERT INTO orders (id, customer, total, ts, lines_json)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        order.order_id,
                        order.customer_id,
                        order.total_cents,
                        order.placed_at.isoformat(),
                        json.dumps(payload),
                    ),
                )
                self._connection.commit()
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            raise PersistenceUnavailable(f"Order storage is unavailable: {exc}") from exc

    def get(self, order_id: str) -> OrderRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
        return None if row is None else _record_from_row(row)

    def list_for_customer(self, customer_id: str) -> list[OrderRecord]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM orders WHERE customer = ? ORDER BY rowid", (customer_id,)
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def count_for_customer(self, customer_id: str) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS n FROM orders WHERE customer = ?", (customer_id,)
            ).fetchone()
        return int(row["n"])


def _record_from_row(row: sqlite3.Row) -> OrderRecord:
    payload = json.loads(row["lines_json"])
    lines = tuple(
        OrderLine(
            sku=item["sku"],
            quantity=item["quantity"],
            unit_price_cents=item["unit_price_cents"],
        )
        for item in payload["lines"]
    )
    subtotal = sum(line.quantity * line.unit_price_cents for line in lines)
    return OrderRecord(
        order_id=row["id"],
        customer_id=row["customer"],
        lines=lines,
        subtotal_cents=subtotal,
        discount_cents=payload["discount_cents"],
        shipping_cents=payload["shipping_cents"],
        total_cents=row["total"],
        placed_at=datetime.fromisoformat(row["ts"]),
    )
