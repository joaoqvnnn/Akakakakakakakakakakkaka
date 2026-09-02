import asyncio
import logging
import sys

from aiogram.types import BotCommand

from bot import create_bot, create_dispatcher
from config import settings
from database.session import init_db, close_db
from webhook import start_webhook_server, set_bot
from tasks.scheduler import start_background_tasks, stop_background_tasks


logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def set_commands(bot):
    commands = [
        BotCommand(command="start", description="Iniciar o bot"),
        BotCommand(command="saldo", description="Ver meu saldo"),
        BotCommand(command="id", description="Ver meu ID"),
        BotCommand(command="pix", description="Gerar PIX — /pix 10"),
        BotCommand(command="admin", description="Painel administrativo"),
        BotCommand(command="termos", description="Termos de uso"),
        BotCommand(command="cancelar", description="Cancelar operação"),
    ]
    await bot.set_my_commands(commands)


async def on_startup(bot):
    logger.info("Iniciando banco de dados...")
    await init_db()
    await set_commands(bot)

    set_bot(bot)
    await start_webhook_server()
    await start_background_tasks()

    logger.info("Bot @%s iniciado.", settings.BOT_USERNAME)


async def on_shutdown(bot):
    logger.info("Encerrando...")
    await stop_background_tasks()
    await close_db()
    await bot.session.close()
    logger.info("Bot finalizado.")


async def main():
    bot = create_bot()
    dp = create_dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Polling + webhook HTTP...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrompido.")
