import asyncio
import logging
from aiogram import Bot, Dispatcher
from bot.config import BOT_TOKEN
from bot.database import load_settings
from bot.image_gen import init_fonts
from bot.handlers import router
from bot.commands import BOT_COMMANDS

async def main():
    logging.basicConfig(level=logging.INFO)
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set!")
        return

    load_settings()
    init_fonts()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    # Автоматически обновляем меню команд в интерфейсе Telegram
    await bot.set_my_commands(BOT_COMMANDS)
    
    logging.info("Bot is starting...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
