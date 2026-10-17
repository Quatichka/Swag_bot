"""Карточка заказа для админов: текст + кнопки с учётом исполнителя и голосов."""
from aiogram.types import InlineKeyboardMarkup

from app import db, keyboards as kb, texts
from app.config import config


async def render(order: db.Order, in_group: bool) -> tuple[str, InlineKeyboardMarkup]:
    # в группе заказ отклоняется голосованием, в личке админа — сразу
    need = config.reject_votes if in_group else None
    voters = await db.votes(order.id) if need and order.status == "new" else []
    return (texts.admin_order_card(order, voters, need),
            kb.admin_order(order.id, order.status, len(voters), need, order.pay_status))
