import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, TelegramObject

from app import billing, cards, db, keyboards as kb, texts
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

def _in_group(call: CallbackQuery) -> bool:
    return call.message.chat.type != "private"


async def _refresh_card(call: CallbackQuery, order: db.Order) -> None:
    text, markup = await cards.render(order, _in_group(call))
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            raise


def _not_assignee(call: CallbackQuery, order: db.Order) -> bool:
    """Заказ уже взял кто-то другой — остальным действия по нему запрещены."""
    return bool(order.assignee_id and call.from_user.id != order.assignee_id)


@router.callback_query(F.data.regexp(r"^adm:(accepted|rejected|done):\d+$"))
async def change_status(call: CallbackQuery, bot: Bot) -> None:
    _, action, order_id = call.data.split(":")
    order = await db.get_order(int(order_id))
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    if _not_assignee(call, order):
        await call.answer(f"Заказ взял {order.assignee_name} — действовать по нему может только он",
                          show_alert=True)
        await _refresh_card(call, order)
        return

    new_status = None
    if action == "accepted":
        if await db.assign(order.id, call.from_user.id, _admin_name(call)):
            new_status = "accepted"
    elif action == "done":
        if order.status == "accepted" and await db.transition(order.id, "accepted", "done"):
            new_status = "done"
    elif order.status == "accepted":
        # старая кнопка «Отменить заказ» на уже отправленных карточках — теперь это «Передать другому»
        await release_order(call)
        return
    elif order.status == "new" and _in_group(call):
        # в группе отклонение — голосованием: нужно REJECT_VOTES разных голосов
        added, voters = await db.toggle_vote(order.id, call.from_user.id, _admin_name(call))
        need = config.reject_votes
        if len(voters) < need:
            await _refresh_card(call, order)
            await call.answer(f"{'Голос за отклонение учтён' if added else 'Голос отозван'}: "
                              f"{len(voters)}/{need}")
            return
        if await db.transition(order.id, "new", "rejected"):
            new_status = "rejected"
    elif order.status == "new":
        if await db.transition(order.id, "new", "rejected"):
            new_status = "rejected"

    order = await db.get_order(order.id)
    await _refresh_card(call, order)
    if not new_status:
        await call.answer(f"Заказ уже в статусе «{order.status_label}»", show_alert=True)
        return
    await call.answer(f"Статус: {order.status_label}")

    image, template = texts.STATUS_NOTIFY[new_status]
    caption = template.format(order_id=order.id, manager=config.manager_username)
    try:
        await send_screen(bot, order.user_id, image, caption, kb.after_order())
    except TelegramAPIError as e:
        log.warning("Клиент %s не получил уведомление: %s", order.user_id, e)
        await call.message.answer(f"⚠️ Не удалось уведомить клиента по заказу #{order.id} "
                                  "(возможно, он заблокировал бота).")


@router.callback_query(F.data.regexp(r"^adm:release:\d+$"))
async def release_order(call: CallbackQuery) -> None:
    """Исполнитель отдаёт заказ: он снова открыт, и взять его может любой."""
    order = await db.get_order(int(call.data.rsplit(":", 1)[1]))
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    if _not_assignee(call, order):
        await call.answer(f"Заказ взял {order.assignee_name} — передать его может только он",
                          show_alert=True)
        await _refresh_card(call, order)
        return
    if not await db.release(order.id, call.from_user.id):
        order = await db.get_order(order.id)
        await _refresh_card(call, order)
        await call.answer(f"Заказ уже в статусе «{order.status_label}»", show_alert=True)
        return

    order = await db.get_order(order.id)
    await _refresh_card(call, order)
    await call.answer("Заказ снова открыт")
    await call.message.reply(
        f"🔄 <b>Заказ #{order.id} снова открыт</b>\n\n"
        f"{escape(_admin_name(call))} передал его. Кто возьмёт — жмите «✅ Принять» под карточкой.")


# ---------- оплата ----------

class AdminInvoice(StatesGroup):
    amount = State()


@router.callback_query(F.data.regexp(r"^adm:invoice:\d+$"))
async def start_invoice(call: CallbackQuery, state: FSMContext) -> None:
    order = await db.get_order(int(call.data.rsplit(":", 1)[1]))
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    if _not_assignee(call, order):
        await call.answer(f"Заказ взял {order.assignee_name} — выставить счёт может только он", show_alert=True)
        return
    if order.status not in ("accepted", "done") or order.pay_status == "paid":
        await call.answer("По этому заказу счёт выставить нельзя", show_alert=True)
        await _refresh_card(call, order)
        return
    await state.set_state(AdminInvoice.amount)
    await state.update_data(invoice_order=order.id)
    await call.answer()
    rate = f"{config.star_rate:g}".replace(".", ",")
    await call.message.answer(
        f"💳 Напиши сумму счёта по заказу #{order.id} в рублях, например <code>1500</code>.\n"
        f"Клиент сможет оплатить по СБП или звёздами (1 ⭐ = {rate} ₽).",
        reply_markup=kb.admin_cancel())


@router.message(AdminInvoice.amount)
async def got_invoice_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    digits = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if not digits or not 1 <= int(digits) <= 1_000_000:
        await message.answer("Нужна сумма в рублях числом, например <code>1500</code>.",
                             reply_markup=kb.admin_cancel())
        return
    order_id = (await state.get_data())["invoice_order"]
    await state.clear()
    order = await db.get_order(order_id)
    if not order or (order.assignee_id and order.assignee_id != message.from_user.id):
        await message.answer("⛔ Выставить счёт по этому заказу может только его исполнитель.")
        return

    rub = int(digits)
    stars = billing.stars_for(rub)
    if not stars and not billing.sbp_enabled():
        await message.answer("⚠️ Эту сумму нельзя оплатить звёздами, а реквизиты СБП не заданы "
                             "(SBP_PHONE в настройках). Счёт не выставлен.")
        return
    if not await db.set_invoice(order.id, rub, stars or 0):
        await message.answer(f"Заказ #{order.id} уже оплачен — счёт не изменён.")
        return
    order = await db.get_order(order.id)
    try:
        await billing.send_choice(bot, order)
    except TelegramAPIError as e:
        await message.answer(f"⚠️ Не удалось отправить счёт клиенту: {e.message}")
        return
    stars_note = f" / {stars} ⭐" if stars else " (звёздами нельзя — слишком большая сумма)"
    await message.answer(f"✅ Счёт по заказу #{order.id} на {rub} ₽{stars_note} отправлен клиенту.")


@router.callback_query(F.data.regexp(r"^adm:(paid|notpaid):\d+$"))
async def confirm_sbp(call: CallbackQuery, bot: Bot) -> None:
    _, action, order_id = call.data.split(":")
    order = await db.get_order(int(order_id))
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    if _not_assignee(call, order):
        await call.answer(f"Заказ взял {order.assignee_name} — подтвердить оплату может только он",
                          show_alert=True)
        return
    if order.pay_status != "claimed":
        await call.answer(f"Оплата уже обработана: {order.pay_label or 'счёт не выставлен'}", show_alert=True)
        await _refresh_card(call, order)
        return

    if action == "paid":
        ok = await db.mark_paid(order.id, "sbp")
        client_text = texts.PAY_DONE.format(order_id=order.id)
        client_kb = kb.after_order()
    else:
        ok = await db.set_pay_status(order.id, "claimed", "invoiced")
        client_text = texts.PAY_NOT_FOUND.format(order_id=order.id, manager=config.manager_username)
        client_kb = kb.pay_choice(order.id, order.price_rub, order.price_stars, billing.sbp_enabled())
    order = await db.get_order(order.id)
    await _refresh_card(call, order)
    if not ok:
        await call.answer("Статус оплаты уже изменился", show_alert=True)
        return
    await call.answer("Оплата подтверждена" if action == "paid" else "Клиенту сообщили, что оплата не найдена")
    try:
        await bot.send_message(order.user_id, client_text, reply_markup=client_kb)
    except TelegramAPIError as e:
        log.warning("Клиент %s не получил уведомление об оплате: %s", order.user_id, e)


# ---------- переписка с клиентом ----------

@router.callback_query(F.data.regexp(r"^adm:(reply|answer):\d+$"))
async def start_reply(call: CallbackQuery, state: FSMContext) -> None:
    _, kind, target = call.data.split(":")
    if kind == "reply":
        order = await db.get_order(int(target))
        if not order:
            await call.answer("Заказ не найден", show_alert=True)
            return
        if _not_assignee(call, order):
            await call.answer(f"Заказ взял {order.assignee_name} — писать клиенту может только он",
                              show_alert=True)
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
    if order_id:  # пока писали ответ, заказ мог взять кто-то другой
        order = await db.get_order(order_id)
        if order and order.assignee_id and order.assignee_id != message.from_user.id:
            await message.answer(f"⛔ Заказ #{order_id} взял {order.assignee_name} — "
                                 "писать клиенту может только он. Сообщение не отправлено.")
            return
    header = (f"<b>💬 Сообщение от SWAG Studio по заказу #{order_id}</b>" if order_id
              else "<b>💬 Ответ от SWAG Studio</b>")
    try:
        await bot.send_message(data["reply_user"], header)
        await message.copy_to(data["reply_user"])
    except TelegramAPIError as e:
        await message.answer(f"⚠️ Не доставлено: {e.message}")
        return
    await message.answer("✅ Отправлено клиенту")
