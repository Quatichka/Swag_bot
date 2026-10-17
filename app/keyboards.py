from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import config

SERVICES = {
    "preview": "🖼 Превью",
    "render": "🧊 Рендер",
    "art": "🎨 Арт",
    "montage": "🎬 Монтаж",
    "skin": "👕 Скин",
    "figure": "🗿 Фигура (Figure Mod)",
    "other": "✨ Другое",
}

DEADLINES = {
    "urgent": "⚡ Срочно (24 ч)",
    "3days": "📅 2–3 дня",
    "week": "🗓 В течение недели",
    "flex": "😌 Не горит",
}

BUDGETS = {
    "b1": "до 500 ₽",
    "b2": "500–1500 ₽",
    "b3": "1500–3000 ₽",
    "b4": "3000 ₽+",
    "talk": "🤝 Обсудим",
}


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _rows(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


def main_menu() -> InlineKeyboardMarkup:
    return _rows(
        [_btn("🛒 Сделать заказ", "order:start")],
        [_btn("💼 Услуги и цены", "menu:services"), _btn("📦 Мои заказы", "menu:orders")],
        [_btn("❓ Задать вопрос", "menu:question")],
        [InlineKeyboardButton(text="🔥 Портфолио / канал", url=config.channel_url)],
    )


def back_to_menu() -> InlineKeyboardMarkup:
    return _rows([_btn("⬅️ В меню", "menu:main")])


def services_menu() -> InlineKeyboardMarkup:
    return _rows([_btn("🛒 Сделать заказ", "order:start")], [_btn("⬅️ В меню", "menu:main")])


def _choices(prefix: str, items: dict[str, str], per_row: int) -> list[list[InlineKeyboardButton]]:
    buttons = [_btn(text, f"{prefix}:{key}") for key, text in items.items()]
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


CANCEL_ROW = [_btn("✖️ Отменить заказ", "order:cancel")]


def order_services() -> InlineKeyboardMarkup:
    return _rows(*_choices("svc", SERVICES, 2), CANCEL_ROW)


def order_step(back: str) -> InlineKeyboardMarkup:
    return _rows([_btn("⬅️ Назад", back)], CANCEL_ROW)


def order_refs(count: int) -> InlineKeyboardMarkup:
    label = f"✅ Готово ({count})" if count else "⏭ Пропустить"
    return _rows([_btn(label, "refs:done")], [_btn("⬅️ Назад", "back:details")], CANCEL_ROW)


def order_deadlines() -> InlineKeyboardMarkup:
    return _rows(*_choices("dl", DEADLINES, 2), [_btn("⬅️ Назад", "back:refs")], CANCEL_ROW)


def order_budgets() -> InlineKeyboardMarkup:
    return _rows(*_choices("bg", BUDGETS, 2), [_btn("⬅️ Назад", "back:deadline")], CANCEL_ROW)


def order_confirm() -> InlineKeyboardMarkup:
    return _rows(
        [_btn("🚀 Отправить заказ", "order:send")],
        [_btn("✏️ Заполнить заново", "order:start")],
        CANCEL_ROW,
    )


def after_order() -> InlineKeyboardMarkup:
    return _rows(
        [_btn("📦 Мои заказы", "menu:orders")],
        [InlineKeyboardButton(text="💬 Написать менеджеру",
                              url=f"https://t.me/{config.manager_username}")],
        [_btn("⬅️ В меню", "menu:main")],
    )


def admin_order(order_id: int, status: str, votes: int = 0, need: int | None = None) -> InlineKeyboardMarkup:
    """Кнопки под карточкой заказа. need — сколько голосов нужно для отклонения (только в группе)."""
    reply = _btn("💬 Написать клиенту", f"adm:reply:{order_id}")
    if status == "new":
        reject = f"❌ Отклонить ({votes}/{need})" if need else "❌ Отклонить"
        return _rows([_btn("✅ Принять", f"adm:accepted:{order_id}"),
                      _btn(reject, f"adm:rejected:{order_id}")], [reply])
    if status == "accepted":
        return _rows([_btn("🏁 Выполнен", f"adm:done:{order_id}"),
                      _btn("🔄 Передать другому", f"adm:release:{order_id}")], [reply])
    return _rows([reply])


def admin_question(user_id: int) -> InlineKeyboardMarkup:
    return _rows([_btn("💬 Ответить", f"adm:answer:{user_id}")])


def admin_cancel() -> InlineKeyboardMarkup:
    return _rows([_btn("✖️ Отмена", "adm:cancel")])
