import asyncio
import logging

from aiogram.types import BotCommand

from bot import create_bot, create_dispatcher
from database.session import init_db
from webhook import start_webhook_server, set_bot
from tasks.scheduler import expire_pix_loop, stop_scheduler
from services.settings_service import SettingsService
from database.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup(bot):
    await init_db()
    async with AsyncSessionLocal() as session:
        await SettingsService.ensure_defaults(session)
        await session.commit()
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Menu principal"),
            BotCommand(command="saldo", description="Ver saldo"),
            BotCommand(command="pix", description="Recarregar PIX"),
            BotCommand(command="historico", description="Compras"),
            BotCommand(command="afiliados", description="Afiliados"),
            BotCommand(command="ranking", description="Ranking"),
            BotCommand(command="alerta", description="Alertas"),
            BotCommand(command="termos", description="Termos"),
            BotCommand(command="id", description="Seu ID"),
            BotCommand(command="admin", description="Painel admin"),
        ]
    )
    set_bot(bot)
    asyncio.create_task(expire_pix_loop(60))
    try:
        await start_webhook_server()
    except Exception:
        logger.exception("Webhook HTTP não subiu (ok em dev sem porta)")
    logger.info("Bot online")


async def on_shutdown(bot):
    stop_scheduler()
    await bot.session.close()


async def main():
    bot = create_bot()
    dp = create_dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
