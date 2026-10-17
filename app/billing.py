"""Оплата заказов: звёзды Telegram (автоматически) и перевод по СБП (с подтверждением исполнителем)."""
import math

from aiogram import Bot

from app import cards, db, keyboards as kb, texts
from app.config import config
from app.routing import deliver

STARS_MAX = 10000  # больше одного счёта в звёздах Telegram не принимает


def stars_for(rub: int) -> int | None:
    """Сумма в звёздах по курсу из настроек; None — если в один счёт не помещается."""
    stars = math.ceil(rub / config.star_rate)
    return stars if 1 <= stars <= STARS_MAX else None


def sbp_enabled() -> bool:
    return bool(config.sbp_phone)


async def send_choice(bot: Bot, order: db.Order) -> None:
    """Отправляет клиенту счёт с выбором способа оплаты."""
    await bot.send_message(order.user_id, texts.invoice_text(order),
                           reply_markup=kb.pay_choice(order.id, order.price_rub, order.price_stars,
                                                      sbp_enabled()))


async def notify_staff(bot: Bot, order: db.Order, header: str) -> None:
    """Сообщает в чат студии (тему заказов) об оплате — карточкой с актуальными кнопками."""
    async def send(target):
        text, markup = await cards.render(order, in_group=target.chat_id < 0)
        await bot.send_message(target.chat_id, f"{header}\n\n{text}", message_thread_id=target.thread_id,
                               reply_markup=markup)
    await deliver("orders", send)
