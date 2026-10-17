"""Чат студии: бота добавляют в группу — он создаёт тему «Заказы»
и дальше присылает туда заказы с кнопками. Вопросы клиентов идут админам в личку.
"""
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, Message

from app import db
from app.config import config

router = Router(name="group")
router.message.filter(F.chat.type.in_({"group", "supergroup"}))
router.my_chat_member.filter(F.chat.type.in_({"group", "supergroup"}))
log = logging.getLogger(__name__)

ORDERS_TOPIC = "📦 Заказы"

HOW_TO = (
    "<b>Почти готово!</b> Чтобы я создал тему для заказов:\n\n"
    "1. Настройки группы → <b>Темы</b> → включить\n"
    "2. Сделайте меня <b>администратором</b> с правом «Управление темами»\n"
    "3. Отправьте /setup\n\n"
    "Пока темы не настроены, заказы будут приходить сюда, в общий чат."
)


async def setup_chat(bot: Bot, chat_id: int, force: bool = False) -> None:
    """Делает чат «чатом студии» и создаёт в нём тему для заказов (если ещё нет или force)."""
    chat = await bot.get_chat(chat_id)
    same_chat = await db.get_setting("staff_chat") == str(chat_id)
    if same_chat and not force and await db.get_setting("orders_thread"):
        return  # тема уже есть

    # сбрасываем старую тему: пока новая не создана, заказы идут в общий чат
    await db.set_settings(staff_chat=chat_id, orders_thread="")

    if not chat.is_forum:
        await bot.send_message(chat_id, HOW_TO)
        return

    try:
        orders = await bot.create_forum_topic(chat_id, ORDERS_TOPIC)
    except TelegramAPIError as e:
        log.warning("Не удалось создать тему в %s: %s", chat_id, e)
        await bot.send_message(chat_id, HOW_TO)
        return

    await db.set_settings(orders_thread=orders.message_thread_id)
    await bot.send_message(
        chat_id, "<b>📦 Сюда будут приходить новые заказы.</b>\n\n"
                 "Под каждым — кнопки «Принять» и «Отклонить». Клиент сразу получит уведомление в боте.",
        message_thread_id=orders.message_thread_id)


@router.my_chat_member()
async def bot_membership_changed(event: ChatMemberUpdated, bot: Bot) -> None:
    status = event.new_chat_member.status
    if status not in ("member", "administrator"):
        if await db.get_setting("staff_chat") == str(event.chat.id):
            await db.set_settings(staff_chat="", orders_thread="")
            log.warning("Бота убрали из чата студии %s — заявки пойдут админам в личку", event.chat.id)
        return

    is_staff_chat = await db.get_setting("staff_chat") == str(event.chat.id)
    if not is_staff_chat and event.from_user.id not in config.admin_ids:
        # в чужие группы не встраиваемся, чтобы заказы не утекли
        await bot.send_message(event.chat.id, "Этот бот работает только в чате SWAG Studio 👋")
        await bot.leave_chat(event.chat.id)
        return

    await setup_chat(bot, event.chat.id)


@router.message(Command("setup"))
async def cmd_setup(message: Message, bot: Bot) -> None:
    if message.from_user.id not in config.admin_ids:
        await message.reply("Настраивать бота могут только админы из ADMIN_IDS.")
        return
    await setup_chat(bot, message.chat.id, force=True)


@router.message(F.migrate_to_chat_id)
async def chat_migrated(message: Message, bot: Bot) -> None:
    """Когда в группе включают темы, Telegram превращает её в супергруппу с новым ID."""
    if await db.get_setting("staff_chat") == str(message.chat.id):
        await setup_chat(bot, message.migrate_to_chat_id)
