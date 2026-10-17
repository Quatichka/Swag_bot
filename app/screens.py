"""Показ «экранов» бота: картинка + подпись + клавиатура.

Если пользователь нажал кнопку под сообщением с картинкой — редактируем это же сообщение,
чтобы чат не засорялся. Если пришёл текст — отправляем новое сообщение.
После первой загрузки картинки кэшируем её file_id, чтобы не грузить файл повторно.
"""
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardMarkup, InputMediaPhoto,
                           Message)

from app.config import config

_file_ids: dict[str, str] = {}


def _photo(key: str) -> str | FSInputFile:
    return _file_ids.get(key) or FSInputFile(config.images_dir / f"{key}.png")


def _remember(key: str, msg: Message | bool) -> None:
    if isinstance(msg, Message) and msg.photo:
        _file_ids[key] = msg.photo[-1].file_id


async def show(event: Message | CallbackQuery, key: str, caption: str,
               kb: InlineKeyboardMarkup | None = None) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer()
        msg = event.message
        if isinstance(msg, Message) and msg.photo:
            try:
                edited = await msg.edit_media(InputMediaPhoto(media=_photo(key), caption=caption),
                                              reply_markup=kb)
                _remember(key, edited)
                return
            except TelegramBadRequest as e:
                if "not modified" in str(e):
                    return
        sent = await msg.answer_photo(_photo(key), caption=caption, reply_markup=kb)
    else:
        sent = await event.answer_photo(_photo(key), caption=caption, reply_markup=kb)
    _remember(key, sent)


async def send_screen(bot: Bot, chat_id: int, key: str, caption: str,
                      kb: InlineKeyboardMarkup | None = None) -> None:
    """Отправить экран в произвольный чат (например, уведомление клиенту о статусе)."""
    sent = await bot.send_photo(chat_id, _photo(key), caption=caption, reply_markup=kb)
    _remember(key, sent)
