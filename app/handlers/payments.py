"""Оплата со стороны клиента: выбор способа, звёзды Telegram, перевод по СБП, /paysupport."""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from app import billing, db, keyboards as kb, texts
from app.config import config

router = Router(name="payments")
log = logging.getLogger(__name__)


async def _own_order(call: CallbackQuery) -> db.Order | None:
    """Заказ из кнопки, если он принадлежит нажавшему и ещё ждёт оплаты."""
    order = await db.get_order(int(call.data.rsplit(":", 1)[1]))
    if not order or order.user_id != call.from_user.id:
        await call.answer("Счёт не найден", show_alert=True)
        return None
    if order.pay_status == "paid":
        await call.answer("Этот заказ уже оплачен ✅", show_alert=True)
        return None
    if order.pay_status == "none" or not order.price_rub:
        await call.answer("Счёт по этому заказу ещё не выставлен", show_alert=True)
        return None
    return order


@router.callback_query(F.data.regexp(r"^pay:choose:\d+$"))
async def pay_choose(call: CallbackQuery) -> None:
    if not (order := await _own_order(call)):
        return
    await call.answer()
    await call.message.edit_text(texts.invoice_text(order),
                                 reply_markup=kb.pay_choice(order.id, order.price_rub, order.price_stars,
                                                            billing.sbp_enabled()))


@router.callback_query(F.data.regexp(r"^pay:stars:\d+$"))
async def pay_stars(call: CallbackQuery, bot: Bot) -> None:
    if not (order := await _own_order(call)):
        return
    if not order.price_stars:
        await call.answer("Эту сумму нельзя оплатить звёздами — выбери СБП", show_alert=True)
        return
    await call.answer()
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"SWAG Studio · заказ #{order.id}",
        description=f"Оплата заказа #{order.id}: {texts.service_label(order.service)}",
        payload=f"order:{order.id}",
        currency="XTR",  # звёзды Telegram — провайдер платежей не нужен
        prices=[LabeledPrice(label=f"Заказ #{order.id}", amount=order.price_stars)],
    )


@router.callback_query(F.data.regexp(r"^pay:sbp:\d+$"))
async def pay_sbp(call: CallbackQuery) -> None:
    if not (order := await _own_order(call)):
        return
    if not billing.sbp_enabled():
        await call.answer("Оплата по СБП сейчас недоступна — выбери звёзды или напиши менеджеру",
                          show_alert=True)
        return
    await call.answer()
    await call.message.edit_text(texts.sbp_text(order, config.sbp_phone, config.sbp_bank, config.sbp_name),
                                 reply_markup=kb.sbp_claim(order.id))


@router.callback_query(F.data.regexp(r"^pay:claim:\d+$"))
async def pay_claim(call: CallbackQuery, bot: Bot) -> None:
    if not (order := await _own_order(call)):
        return
    if not await db.set_pay_status(order.id, "invoiced", "claimed", method="sbp"):
        await call.answer("Мы уже проверяем оплату — бот напишет, как только её подтвердят", show_alert=True)
        return
    await call.answer("Спасибо! Проверяем оплату")
    await call.message.edit_text(texts.PAY_CLAIMED.format(order_id=order.id))
    order = await db.get_order(order.id)
    await billing.notify_staff(bot, order, f"🏦 <b>Клиент сообщил об оплате заказа #{order.id} по СБП "
                                           f"({order.price_rub} ₽).</b> Проверьте поступление.")


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, bot: Bot) -> None:
    """Telegram спрашивает, можно ли проводить оплату звёздами, — сверяем с заказом."""
    order = None
    if query.invoice_payload.startswith("order:"):
        order = await db.get_order(int(query.invoice_payload.split(":")[1]))
    if not order or order.user_id != query.from_user.id:
        await query.answer(ok=False, error_message="Счёт не найден. Открой счёт заново из бота.")
    elif order.pay_status == "paid":
        await query.answer(ok=False, error_message="Этот заказ уже оплачен.")
    elif query.currency != "XTR" or query.total_amount != order.price_stars:
        await query.answer(ok=False, error_message="Сумма счёта изменилась — открой новый счёт в боте.")
    else:
        await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot) -> None:
    payment = message.successful_payment
    order_id = int(payment.invoice_payload.split(":")[1])
    if not await db.mark_paid(order_id, "stars", payment.telegram_payment_charge_id):
        log.warning("Повторное уведомление об оплате заказа #%s", order_id)
        return
    await message.answer(texts.PAY_DONE.format(order_id=order_id), reply_markup=kb.after_order())
    order = await db.get_order(order_id)
    await billing.notify_staff(bot, order, f"💰 <b>Заказ #{order_id} оплачен звёздами: "
                                           f"{payment.total_amount} ⭐</b>")


@router.message(Command("paysupport"))
async def pay_support(message: Message) -> None:
    await message.answer(texts.PAY_SUPPORT.format(manager=config.manager_username))
