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
CREATE TABLE IF NOT EXISTS order_votes (
    order_id INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    name     TEXT NOT NULL,
    PRIMARY KEY (order_id, user_id)
);
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
    assignee_id: int | None = None    # кто взял заказ — только он может дальше с ним работать
    assignee_name: str | None = None

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
        # миграция старой базы: колонки исполнителя появились позже
        cur = await db.execute("PRAGMA table_info(orders)")
        columns = {row[1] for row in await cur.fetchall()}
        if "assignee_id" not in columns:
            await db.execute("ALTER TABLE orders ADD COLUMN assignee_id INTEGER")
        if "assignee_name" not in columns:
            await db.execute("ALTER TABLE orders ADD COLUMN assignee_name TEXT")
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


async def transition(order_id: int, old: str, new: str) -> bool:
    """Меняет статус, только если он всё ещё old — защита от двойного нажатия разными людьми."""
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute("UPDATE orders SET status = ? WHERE id = ? AND status = ?", (new, order_id, old))
        await db.commit()
        return cur.rowcount == 1


async def assign(order_id: int, user_id: int, name: str) -> bool:
    """Берёт новый заказ в работу. False — если его уже кто-то взял или он закрыт."""
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute(
            "UPDATE orders SET status = 'accepted', assignee_id = ?, assignee_name = ?"
            " WHERE id = ? AND status = 'new'", (user_id, name, order_id))
        await db.execute("DELETE FROM order_votes WHERE order_id = ?", (order_id,))
        await db.commit()
        return cur.rowcount == 1


async def release(order_id: int, user_id: int) -> bool:
    """Исполнитель отдаёт заказ: он снова «новый» и без исполнителя. False — если заказ уже не его."""
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute(
            "UPDATE orders SET status = 'new', assignee_id = NULL, assignee_name = NULL"
            " WHERE id = ? AND status = 'accepted' AND (assignee_id = ? OR assignee_id IS NULL)",
            (order_id, user_id))
        await db.execute("DELETE FROM order_votes WHERE order_id = ?", (order_id,))
        await db.commit()
        return cur.rowcount == 1


async def votes(order_id: int) -> list[str]:
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute("SELECT name FROM order_votes WHERE order_id = ? ORDER BY rowid", (order_id,))
        return [row[0] for row in await cur.fetchall()]


async def toggle_vote(order_id: int, user_id: int, name: str) -> tuple[bool, list[str]]:
    """Голос за отклонение: повторное нажатие отзывает голос. Возвращает (добавлен ли, все голоса)."""
    async with aiosqlite.connect(config.db_path) as db:
        cur = await db.execute("DELETE FROM order_votes WHERE order_id = ? AND user_id = ?", (order_id, user_id))
        added = cur.rowcount == 0
        if added:
            await db.execute("INSERT INTO order_votes (order_id, user_id, name) VALUES (?, ?, ?)",
                             (order_id, user_id, name))
        await db.commit()
    return added, await votes(order_id)


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
