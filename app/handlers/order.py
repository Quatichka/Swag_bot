import asyncio
from collections import defaultdict

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InputMediaDocument, InputMediaPhoto, InputMediaVideo,
                           Message)

from app import cards, db, keyboards as kb, texts
from app.routing import deliver
from app.handlers.common import show_welcome
from app.screens import show

router = Router(name="order")

# Альбом из нескольких фото приходит пачкой апдейтов, которые обрабатываются параллельно —
# лочим по пользователю, чтобы не потерять вложения при записи в FSM.
_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


class OrderForm(StatesGroup):
    details = State()
    refs = State()
    deadline = State()
    budget = State()
    confirm = State()


# ---------- шаг 1: услуга ----------

@router.callback_query(F.data == "order:start")
async def order_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show(call, "order_service", texts.ORDER_SERVICE, kb.order_services())


@router.callback_query(F.data == "order:cancel")
async def order_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await show_welcome(call, state)


@router.callback_query(F.data.startswith("svc:"))
async def choose_service(call: CallbackQuery, state: FSMContext) -> None:
    service = call.data.split(":", 1)[1]
    await state.update_data(service=service, attachments=[])
    await ask_details(call, state)


# ---------- шаг 2: описание ----------

async def ask_details(event: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if "service" not in data:  # анкета потерялась (например, бот перезапускался)
        await order_start(event, state) if isinstance(event, CallbackQuery) else await show_welcome(event, state)
        return
    await state.set_state(OrderForm.details)
    caption = texts.ORDER_DETAILS.format(service=texts.service_label(data["service"]))
    await show(event, "order_details", caption, kb.order_step("order:start"))


@router.callback_query(F.data == "back:details")
async def back_details(call: CallbackQuery, state: FSMContext) -> None:
    await ask_details(call, state)


def _attachment(message: Message) -> list[str] | None:
    if message.photo:
        return ["photo", message.photo[-1].file_id]
    if message.document:
        return ["document", message.document.file_id]
    if message.video:
        return ["video", message.video.file_id]
    return None


@router.message(OrderForm.details)
async def got_details(message: Message, state: FSMContext) -> None:
    text = (message.text or message.caption or "").strip()
    if len(text) < 5:
        await message.answer("✍️ Опиши задачу текстом — хотя бы пару слов.")
        return
    data = await state.get_data()
    attachments = data.get("attachments", [])
    if att := _attachment(message):
        attachments.append(att)
    await state.update_data(description=text, attachments=attachments)
    await ask_refs(message, state)


# ---------- шаг 3: референсы ----------

async def ask_refs(event: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(OrderForm.refs)
    await show(event, "order_refs", texts.ORDER_REFS, kb.order_refs(len(data.get("attachments", []))))


@router.callback_query(F.data == "back:refs")
async def back_refs(call: CallbackQuery, state: FSMContext) -> None:
    await ask_refs(call, state)


@router.message(OrderForm.refs)
async def got_ref(message: Message, state: FSMContext) -> None:
    att = _attachment(message)
    if att is None and message.text:
        att = ["link", message.text.strip()]
    if att is None:
        await message.answer("Этот тип файла не поддерживается — пришли фото, видео, файл или ссылку.")
        return

    async with _locks[message.from_user.id]:
        data = await state.get_data()
        attachments = data.get("attachments", [])
        attachments.append(att)
        # на альбом отвечаем один раз, а не на каждое фото
        is_new_group = not message.media_group_id or message.media_group_id != data.get("last_group")
        await state.update_data(attachments=attachments, last_group=message.media_group_id)

    if is_new_group:
        await message.answer("📎 Принято! Можно добавить ещё или нажать «Готово».",
                             reply_markup=kb.order_refs(len(attachments)))


@router.callback_query(F.data == "refs:done", OrderForm.refs)
async def refs_done(call: CallbackQuery, state: FSMContext) -> None:
    await ask_deadline(call, state)


# ---------- шаг 4: сроки ----------

async def ask_deadline(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderForm.deadline)
    await show(event, "order_deadline", texts.ORDER_DEADLINE, kb.order_deadlines())


@router.callback_query(F.data == "back:deadline")
async def back_deadline(call: CallbackQuery, state: FSMContext) -> None:
    await ask_deadline(call, state)


@router.callback_query(F.data.startswith("dl:"), OrderForm.deadline)
async def deadline_button(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(deadline=kb.DEADLINES.get(call.data[3:], call.data[3:]))
    await ask_budget(call, state)


@router.message(OrderForm.deadline, F.text)
async def deadline_text(message: Message, state: FSMContext) -> None:
    await state.update_data(deadline=texts.cut(message.text.strip(), 100))
    await ask_budget(message, state)


# ---------- шаг 5: бюджет ----------

async def ask_budget(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderForm.budget)
    await show(event, "order_budget", texts.ORDER_BUDGET, kb.order_budgets())


@router.callback_query(F.data.startswith("bg:"), OrderForm.budget)
async def budget_button(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(budget=kb.BUDGETS.get(call.data[3:], call.data[3:]))
    await ask_confirm(call, state)


@router.message(OrderForm.budget, F.text)
async def budget_text(message: Message, state: FSMContext) -> None:
    await state.update_data(budget=texts.cut(message.text.strip(), 100))
    await ask_confirm(message, state)


# ---------- подтверждение и отправка ----------

async def ask_confirm(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderForm.confirm)
    await show(event, "order_confirm", texts.order_summary(await state.get_data()), kb.order_confirm())


@router.callback_query(F.data == "order:send", OrderForm.confirm)
async def order_send(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    user = call.from_user
    order_id = await db.create_order(
        user_id=user.id, username=user.username, full_name=user.full_name,
        service=data["service"], description=data["description"],
        attachments=data.get("attachments", []), deadline=data["deadline"], budget=data["budget"],
    )
    await state.clear()
    await show(call, "order_success", texts.ORDER_SUCCESS.format(order_id=order_id), kb.after_order())

    order = await db.get_order(order_id)
    await deliver("orders", lambda t: notify_admins(bot, t.chat_id, order, t.thread_id))


async def notify_admins(bot: Bot, chat_id: int, order: db.Order, thread_id: int | None = None) -> None:
    text, markup = await cards.render(order, in_group=chat_id < 0)
    card = await bot.send_message(chat_id, text, message_thread_id=thread_id, reply_markup=markup)

    # фото и видео можно слать одним альбомом, документы — отдельным
    visual = [InputMediaPhoto(media=fid) if t == "photo" else InputMediaVideo(media=fid)
              for t, fid in order.attachments if t in ("photo", "video")]
    docs = [InputMediaDocument(media=fid) for t, fid in order.attachments if t == "document"]
    for group in (visual, docs):
        for i in range(0, len(group), 10):  # лимит Telegram — 10 файлов в альбоме
            await bot.send_media_group(chat_id, group[i:i + 10], message_thread_id=thread_id,
                                       reply_to_message_id=card.message_id)


@router.callback_query(F.data.startswith(("svc:", "dl:", "bg:", "refs:", "order:send")))
async def stale_button(call: CallbackQuery) -> None:
    await call.answer("Эта анкета уже неактуальна — начни заказ заново из меню.", show_alert=True)
