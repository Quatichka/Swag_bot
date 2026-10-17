import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import db, keyboards as kb, texts
from app.config import config
from app.screens import show

router = Router(name="common")
log = logging.getLogger(__name__)


class Ask(StatesGroup):
    question = State()


async def show_welcome(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    name = escape(event.from_user.first_name or "друг")
    await show(event, "welcome", texts.WELCOME.format(name=name), kb.main_menu())


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await show_welcome(message, state)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await show_welcome(message, state)


@router.callback_query(F.data == "menu:main")
async def menu_main(call: CallbackQuery, state: FSMContext) -> None:
    await show_welcome(call, state)


@router.callback_query(F.data == "menu:services")
async def menu_services(call: CallbackQuery) -> None:
    await show(call, "services", texts.SERVICES_TEXT, kb.services_menu())


@router.message(Command("orders"))
@router.callback_query(F.data == "menu:orders")
async def menu_orders(event: Message | CallbackQuery) -> None:
    orders = await db.user_orders(event.from_user.id)
    caption = texts.my_orders_text(orders) if orders else texts.NO_ORDERS
    menu = kb.back_to_menu() if orders else kb.services_menu()
    await show(event, "my_orders", caption, menu)


@router.callback_query(F.data == "menu:question")
async def menu_question(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Ask.question)
    await show(call, "question", texts.QUESTION.format(manager=config.manager_username),
               kb.back_to_menu())


@router.message(Ask.question)
async def got_question(message: Message, state: FSMContext, bot: Bot) -> None:
    user = message.from_user
    header = f"<b>❓ Новый вопрос</b>\nОт: {texts.user_link(user.id, user.full_name, user.username)}"

    # вопрос уходит каждому админу в личку, ответ — кнопкой «Ответить» под сообщением
    delivered = 0
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, header)
            await message.copy_to(admin_id, reply_markup=kb.admin_question(user.id))
            delivered += 1
        except TelegramAPIError as e:
            log.warning("Вопрос не доставлен админу %s (он должен хотя бы раз нажать /start): %s",
                        admin_id, e)
    if not delivered:
        await message.answer("😔 Не получилось передать вопрос. Напиши менеджеру напрямую: "
                             f"@{config.manager_username}")
        return
    await state.clear()
    await show(message, "question", texts.QUESTION_SENT, kb.back_to_menu())


@router.message(StateFilter(None), F.chat.type == "private")
async def fallback(message: Message, state: FSMContext) -> None:
    """Любое сообщение вне сценария — показываем меню."""
    await show_welcome(message, state)
