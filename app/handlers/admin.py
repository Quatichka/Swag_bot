import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, TelegramObject

from app import db, keyboards as kb, texts
from app.config import config
from app.routing import staff_chat_id
from app.screens import send_screen

router = Router(name="admin")
log = logging.getLogger(__name__)


class IsAdmin(BaseFilter):
    """Админ из ADMIN_IDS — везде; любой участник чата студии — внутри этого чата."""

    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        if user.id in config.admin_ids:
            return True
        msg = event.message if isinstance(event, CallbackQuery) else event
        chat = getattr(msg, "chat", None)
        return bool(chat and chat.type != "private" and chat.id == await staff_chat_id())


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class AdminReply(StatesGroup):
    text = State()


def _admin_name(call: CallbackQuery) -> str:
    u = call.from_user
    return f"@{u.username}" if u.username else u.full_name


# ---------- команды ----------

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    counts = await db.stats()
    new_orders = await db.recent_orders(limit=15, status="new")
    lines = [f"{label}: <b>{counts.get(key, 0)}</b>" for key, label in db.STATUSES.items()]
    text = "<b>📊 Панель SWAG Studio</b>\n\n" + "\n".join(lines)
    if new_orders:
        text += "\n\n<b>Ждут ответа:</b>\n" + "\n".join(
            f"/order_{o.id} · {texts.service_label(o.service)} · {o.created_at}" for o in new_orders)
    text += "\n\n<i>Открыть заказ: /order_НОМЕР · последние заказы: /last</i>"
    await message.answer(text)


@router.message(Command("last"))
async def cmd_last(message: Message) -> None:
    orders = await db.recent_orders(limit=20)
    if not orders:
        await message.answer("Заказов пока нет.")
        return
    await message.answer("<b>Последние заказы</b>\n\n" + "\n".join(
        f"/order_{o.id} · {texts.service_label(o.service)} · {o.status_label}" for o in orders))


@router.message(F.text.regexp(r"^/order_(\d+)"))
@router.message(Command("order"))
async def cmd_order(message: Message, command: CommandObject | None = None) -> None:
    raw = command.args if command and command.args else message.text.split("_", 1)[-1].split("@")[0]
    if not raw.strip().isdigit():
        await message.answer("Формат: /order_12 или /order 12")
        return
    order = await db.get_order(int(raw))
    if not order:
        await message.answer("Заказ не найден.")
        return
    from app.handlers.order import notify_admins  # повторно показываем карточку с вложениями
    thread = message.message_thread_id if message.is_topic_message else None
    await notify_admins(message.bot, message.chat.id, order, thread)


# ---------- смена статуса ----------

@router.callback_query(F.data.regexp(r"^adm:(accepted|rejected|done):\d+$"))
async def change_status(call: CallbackQuery, bot: Bot) -> None:
    _, status, order_id = call.data.split(":")
    order = await db.get_order(int(order_id))
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    allowed = {"accepted": "new", "rejected": "new", "done": "accepted"}
    if order.status != allowed[status]:
        await call.answer(f"Заказ уже в статусе «{order.status_label}»", show_alert=True)
        await call.message.edit_text(texts.admin_order_card(order),
                                     reply_markup=kb.admin_order(order.id, order.status))
        return

    await db.set_status(order.id, status)
    order.status = status
    await call.message.edit_text(texts.admin_order_card(order, handled_by=_admin_name(call)),
                                 reply_markup=kb.admin_order(order.id, status))
    await call.answer(f"Статус: {order.status_label}")

    image, template = texts.STATUS_NOTIFY[status]
    caption = template.format(order_id=order.id, manager=config.manager_username)
    try:
        await send_screen(bot, order.user_id, image, caption, kb.after_order())
    except TelegramAPIError as e:
        log.warning("Клиент %s не получил уведомление: %s", order.user_id, e)
        await call.message.answer(f"⚠️ Не удалось уведомить клиента по заказу #{order.id} "
                                  "(возможно, он заблокировал бота).")


# ---------- переписка с клиентом ----------

@router.callback_query(F.data.regexp(r"^adm:(reply|answer):\d+$"))
async def start_reply(call: CallbackQuery, state: FSMContext) -> None:
    _, kind, target = call.data.split(":")
    if kind == "reply":
        order = await db.get_order(int(target))
        if not order:
            await call.answer("Заказ не найден", show_alert=True)
            return
        await state.update_data(reply_user=order.user_id, reply_order=order.id)
        who = f"клиенту по заказу #{order.id}"
    else:
        await state.update_data(reply_user=int(target), reply_order=None)
        who = "на вопрос"
    await state.set_state(AdminReply.text)
    await call.answer()
    await call.message.answer(f"✍️ Напиши ответ {who} одним сообщением (текст, фото, файл):",
                              reply_markup=kb.admin_cancel())


@router.callback_query(F.data == "adm:cancel")
async def cancel_reply(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.answer("Отменено")
    await call.message.delete()


@router.message(AdminReply.text)
async def send_reply(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    order_id = data.get("reply_order")
    header = (f"<b>💬 Сообщение от SWAG Studio по заказу #{order_id}</b>" if order_id
              else "<b>💬 Ответ от SWAG Studio</b>")
    try:
        await bot.send_message(data["reply_user"], header)
        await message.copy_to(data["reply_user"])
    except TelegramAPIError as e:
        await message.answer(f"⚠️ Не доставлено: {e.message}")
        return
    await message.answer("✅ Отправлено клиенту")
