import json
from dataclasses import dataclass
from datetime import datetime

import aiosqlite

from app.config import config

STATUSES = {
    "new": "🆕 Новый",
    "accepted": "🛠 В работе",
    "done": "✅ Выполнен",
    "rejected": "❌ Отклонён",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    username    TEXT,
    full_name   TEXT,
    service     TEXT NOT NULL,
    description TEXT NOT NULL,
    attachments TEXT NOT NULL DEFAULT '[]',
    deadline    TEXT NOT NULL,
    budget      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class Order:
    id: int
    user_id: int
    username: str | None
    full_name: str | None
    service: str
    description: str
    attachments: list[list[str]]  # [[type, file_id], ...], type: photo | document | video
    deadline: str
    budget: str
    status: str
    created_at: str

    @property
    def status_label(self) -> str:
        return STATUSES.get(self.status, self.status)


def _row_to_order(row: aiosqlite.Row) -> Order:
    data = dict(row)
    data["attachments"] = json.loads(data["attachments"])
    return Order(**data)


async def init_db() -> None:
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(config.db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def create_order(user_id: int, username: str | None, full_name: str, service: str,
                       description: str, attachments: list, deadline: str, budget: str) -> int:
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute(
            "INSERT INTO orders (user_id, username, full_name, service, description, attachments,"
            " deadline, budget, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, full_name, service, description, json.dumps(attachments),
             deadline, budget, datetime.now().strftime("%d.%m.%Y %H:%M")),
        )
        await db.commit()
        return cur.lastrowid


async def get_order(order_id: int) -> Order | None:
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return _row_to_order(row) if row else None


async def set_status(order_id: int, status: str) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()


async def user_orders(user_id: int, limit: int = 10) -> list[Order]:
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        return [_row_to_order(r) for r in await cur.fetchall()]


async def recent_orders(limit: int = 10, status: str | None = None) -> list[Order]:
    async with aiosqlite.connect(config.db_path) as db:
        db.row_factory = aiosqlite.Row
        if status:
            cur = await db.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
        else:
            cur = await db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
        return [_row_to_order(r) for r in await cur.fetchall()]


async def stats() -> dict[str, int]:
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
        return {status: count for status, count in await cur.fetchall()}


async def get_setting(key: str) -> str | None:
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_settings(**values: str | int) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(k, str(v)) for k, v in values.items()])
        await db.commit()
