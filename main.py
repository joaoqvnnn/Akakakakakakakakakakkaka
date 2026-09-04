import asyncio
import logging
import os

from aiohttp import web

from bot import create_bot, create_dispatcher
from config import settings
from database.session import init_db
from services.settings_service import SettingsService
from database.session import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup(bot):
    await init_db()
    async with AsyncSessionLocal() as session:
        await SettingsService.ensure_defaults(session)
        await session.commit()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started (polling + web)")


async def health(request):
    return web.json_response({"ok": True, "service": "larizinha"})


def create_web_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    # rotas opcionais se existirem
    try:
        from handlers.order_web import setup_order_web_routes
        setup_order_web_routes(app)
    except Exception as e:
        logger.warning("order_web skip: %s", e)

    try:
        from web_routes import setup_web_routes
        setup_web_routes(app)
    except Exception as e:
        logger.warning("web_routes skip: %s", e)

    return app


async def main():
    bot = create_bot()
    dp = create_dispatcher()

    await on_startup(bot)

    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()

    port = int(os.getenv("PORT") or getattr(settings, "WEBHOOK_PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("HTTP listening on 0.0.0.0:%s", port)

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
