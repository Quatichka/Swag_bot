"""Все тексты бота в одном месте — правьте здесь, не трогая логику."""
from html import escape

from app.db import Order
from app.keyboards import SERVICES

WELCOME = (
    "<b>Йоу, {name}! Это SWAG Studio</b> 💋\n\n"
    "Студия дизайна, где ты получишь <b>превью, рендер, арт, монтаж, скин или фигуру</b> — "
    "быстро, качественно и за адекватную цену.\n\n"
    "Жми <b>«Сделать заказ»</b> — заполнишь короткую анкету, и мы свяжемся с тобой."
)

SERVICES_TEXT = (
    "<b>💼 Наши услуги</b>\n\n"
    "🖼 <b>Превью</b> — обложки для YouTube, Twitch, TikTok, которые цепляют взгляд\n"
    "🧊 <b>Рендер</b> — 3D-сцены, персонажи, предметы\n"
    "🎨 <b>Арт</b> — аватарки, баннеры, иллюстрации, оформление каналов\n"
    "🎬 <b>Монтаж</b> — ролики, шортсы, клипы, эдиты\n"
    "👕 <b>Скин</b> — скин для персонажа по твоей идее или референсу\n"
    "🗿 <b>Фигура</b> — 3D-модель персонажа для Figure Mod\n"
    "✨ <b>Другое</b> — расскажи идею, придумаем\n\n"
    "💰 Стоимость зависит от сложности и сроков — точную цену назовёт менеджер "
    "после того, как посмотрит заказ."
)

ORDER_SERVICE = "<b>Шаг 1/5 · Услуга</b>\n\nЧто тебе нужно?"

ORDER_DETAILS = (
    "<b>Шаг 2/5 · Описание</b>\n\n"
    "Выбрано: {service}\n\n"
    "Опиши задачу одним сообщением: что должно быть на работе, тексты, стиль, цвета, "
    "для какой площадки, размер/длительность. Чем подробнее — тем лучше 👇"
)

ORDER_REFS = (
    "<b>Шаг 3/5 · Референсы</b>\n\n"
    "Отправь примеры, которые нравятся: картинки, файлы, видео или ссылки.\n"
    "Можно несколько сообщений. Когда закончишь — жми «Готово».\n"
    "Нет референсов? Жми «Пропустить»."
)

ORDER_DEADLINE = (
    "<b>Шаг 4/5 · Сроки</b>\n\n"
    "Когда нужна работа? Выбери вариант или напиши дату сообщением."
)

ORDER_BUDGET = (
    "<b>Шаг 5/5 · Бюджет</b>\n\n"
    "На какую сумму рассчитываешь? Выбери вариант или напиши свою."
)

ORDER_SUCCESS = (
    "<b>🔥 Заказ #{order_id} отправлен!</b>\n\n"
    "Менеджер уже получил заявку и скоро напишет тебе в личку. "
    "Статус заказа можно посмотреть в разделе «Мои заказы» — "
    "а ещё бот сам пришлёт уведомление, когда заказ возьмут в работу."
)

QUESTION = (
    "<b>❓ Вопрос студии</b>\n\n"
    "Напиши свой вопрос одним сообщением — мы ответим прямо здесь, в боте.\n"
    "Или пиши менеджеру напрямую: @{manager}"
)

QUESTION_SENT = "<b>✅ Вопрос отправлен!</b>\n\nОтвет придёт сюда, в этот чат."

NO_ORDERS = "<b>📦 Мои заказы</b>\n\nПока пусто. Самое время сделать первый заказ 😉"

STATUS_NOTIFY = {
    "accepted": ("status_accepted",
                 "<b>🛠 Заказ #{order_id} взят в работу!</b>\n\n"
                 "Дизайнер уже начал. Если появятся вопросы — менеджер напишет тебе."),
    "done": ("status_done",
             "<b>✅ Заказ #{order_id} выполнен!</b>\n\n"
             "Спасибо, что выбрал SWAG Studio 💋 Будем рады отзыву и новым заказам!"),
    "rejected": ("status_rejected",
                 "<b>❌ Заказ #{order_id} отклонён</b>\n\n"
                 "К сожалению, сейчас мы не можем взять этот заказ. "
                 "Напиши менеджеру @{manager} — обсудим варианты."),
}


def service_label(key: str) -> str:
    return SERVICES.get(key, key)


def cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def user_link(user_id: int, full_name: str | None, username: str | None) -> str:
    name = escape(full_name or "Клиент")
    link = f'<a href="tg://user?id={user_id}">{name}</a>'
    return f"{link} (@{escape(username)})" if username else f"{link} (без username, id {user_id})"


def order_summary(data: dict) -> str:
    """Превью заказа для клиента перед отправкой (подпись к фото — максимум 1024 символа)."""
    return (
        "<b>Проверь заказ 👀</b>\n\n"
        f"🧩 <b>Услуга:</b> {service_label(data['service'])}\n"
        f"📝 <b>Описание:</b> {escape(cut(data['description'], 450))}\n"
        f"📎 <b>Референсы:</b> {len(data.get('attachments', []))}\n"
        f"⏰ <b>Срок:</b> {escape(data['deadline'])}\n"
        f"💰 <b>Бюджет:</b> {escape(data['budget'])}\n\n"
        "Всё верно? Жми «Отправить заказ»."
    )


def admin_order_card(order: Order, handled_by: str | None = None) -> str:
    links = [a[1] for a in order.attachments if a[0] == "link"]
    files = len(order.attachments) - len(links)
    text = (
        f"<b>{order.status_label} · Заказ #{order.id}</b>\n\n"
        f"👤 <b>Клиент:</b> {user_link(order.user_id, order.full_name, order.username)}\n"
        f"🧩 <b>Услуга:</b> {service_label(order.service)}\n"
        f"⏰ <b>Срок:</b> {escape(order.deadline)}\n"
        f"💰 <b>Бюджет:</b> {escape(order.budget)}\n"
        f"🕒 <b>Создан:</b> {order.created_at}\n"
        f"📎 <b>Файлов:</b> {files}\n\n"
        f"📝 <b>Описание:</b>\n{escape(cut(order.description, 2500))}"
    )
    if links:
        text += "\n\n🔗 <b>Ссылки / комментарии:</b>\n" + "\n".join(
            escape(cut(link, 300)) for link in links[:10])
    if handled_by:
        text += f"\n\n<i>Последнее действие: {escape(handled_by)}</i>"
    return text


def my_orders_text(orders: list[Order]) -> str:
    lines = [
        f"<b>#{o.id}</b> · {service_label(o.service)} · {o.status_label}\n<i>{o.created_at}</i>"
        for o in orders
    ]
    return "<b>📦 Мои заказы</b>\n\n" + "\n\n".join(lines)
