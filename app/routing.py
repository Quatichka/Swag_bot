"""Куда бот отправляет заказы. Вопросы клиентов всегда идут админам в личку (handlers/common.py).

1. Если бота добавили в чат студии и он создал тему — в тему «Заказы».
2. Иначе — в ADMIN_CHAT_ID из .env, если задан.
3. Иначе — каждому админу из ADMIN_IDS в личку.
Если отправить в чат не получилось (тему удалили, бота выгнали), заявка уходит админам в личку.
"""
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from aiogram.exceptions import TelegramAPIError

from app import db
from app.config import config

log = logging.getLogger(__name__)

Kind = Literal["orders"]


@dataclass(frozen=True)
class Target:
    chat_id: int
    thread_id: int | None = None


async def staff_chat_id() -> int | None:
    chat = await db.get_setting("staff_chat")
    return int(chat) if chat else config.admin_chat_id


async def targets(kind: Kind) -> list[Target]:
    chat = await db.get_setting("staff_chat")
    if chat:
        thread = await db.get_setting(f"{kind}_thread")
        return [Target(int(chat), int(thread) if thread else None)]
    return [Target(chat_id) for chat_id in config.notify_targets]


async def deliver(kind: Kind, send: Callable[[Target], Awaitable[None]]) -> None:
    group_failed = False
    for target in await targets(kind):
        try:
            await send(target)
        except TelegramAPIError as e:
            log.warning("Не удалось отправить в чат %s (тема %s): %s", target.chat_id, target.thread_id, e)
            group_failed = group_failed or target.chat_id < 0
    if group_failed:  # запасной канал — личка админов
        for admin_id in config.admin_ids:
            try:
                await send(Target(admin_id))
            except TelegramAPIError as e:
                log.warning("Админ %s тоже недоступен: %s", admin_id, e)
