import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import config
from app.db import init_db
from app.handlers import admin, common, group, order


async def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await init_db()

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    # admin — первым, чтобы ответ админа клиенту не перехватили пользовательские сценарии
    dp.include_routers(admin.router, group.router, order.router, common.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="orders", description="Мои заказы"),
        BotCommand(command="cancel", description="Отменить и вернуться в меню"),
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("SWAG Studio bot запущен")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
