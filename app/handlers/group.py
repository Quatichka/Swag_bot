"""Чат студии: бота добавляют в группу, админ пишет /setup в нужной теме —
и дальше все новые заказы приходят туда с кнопками. Вопросы клиентов идут админам в личку.
"""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, Message

from app import db
from app.config import config

router = Router(name="group")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))
router.my_chat_member.filter(F.chat.type.in_({"group", "supergroup"}))
log = logging.getLogger(__name__)

HOW_TO = (
    "👋 <b>Привет! Я бот SWAG Studio.</b>\n\n"
    "Напишите /setup в той теме, куда присылать новые заказы, — "
    "и они будут приходить туда с кнопками «Принять» и «Отклонить».\n\n"
    "Чтобы я видел сообщения в группе, сделайте меня администратором."
)


async def bind_orders(bot: Bot, chat_id: int, thread_id: int | None) -> None:
    """Запоминает чат и тему для заказов и подтверждает это сообщением в теме."""
    await db.set_settings(staff_chat=chat_id, orders_thread=thread_id or "")
    where = "эту тему" if thread_id else "этот чат"
    await bot.send_message(
        chat_id, f"✅ <b>Готово! Новые заказы будут приходить в {where}.</b>\n\n"
                 "Под каждым — кнопки «Принять» и «Отклонить». Клиент сразу получит уведомление в боте.\n"
                 "Чтобы перенести заказы в другую тему, напишите /setup там.",
        message_thread_id=thread_id)


@router.my_chat_member()
async def bot_membership_changed(event: ChatMemberUpdated, bot: Bot) -> None:
    status = event.new_chat_member.status
    is_staff_chat = await db.get_setting("staff_chat") == str(event.chat.id)

    if status not in ("member", "administrator"):
        if is_staff_chat:
            await db.set_settings(staff_chat="", orders_thread="")
            log.warning("Бота убрали из чата студии %s — заказы пойдут админам в личку", event.chat.id)
        return

    if not is_staff_chat and event.from_user.id not in config.admin_ids:
        # в чужие группы не встраиваемся, чтобы заказы не утекли
        await bot.send_message(event.chat.id, "Этот бот работает только в чате SWAG Studio 👋")
        await bot.leave_chat(event.chat.id)
        return

    old = event.old_chat_member.status
    if old in ("left", "kicked"):  # только что добавили — подсказываем, что делать дальше
        await bot.send_message(event.chat.id, HOW_TO)


@router.message(Command("setup"))
async def cmd_setup(message: Message, bot: Bot) -> None:
    if message.from_user.id not in config.admin_ids:
        await message.reply("Настраивать бота могут только админы из ADMIN_IDS.")
        return
    # в группе с темами берём тему, где написали команду; в «Общем» и обычной группе — весь чат
    thread_id = message.message_thread_id if message.is_topic_message else None
    await bind_orders(bot, message.chat.id, thread_id)


@router.message(F.migrate_to_chat_id)
async def chat_migrated(message: Message) -> None:
    """Когда в группе включают темы, Telegram превращает её в супергруппу с новым ID."""
    if await db.get_setting("staff_chat") == str(message.chat.id):
        await db.set_settings(staff_chat=message.migrate_to_chat_id, orders_thread="")
