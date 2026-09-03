from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from middlewares.database import DatabaseMiddleware
from middlewares.user import UserMiddleware
from middlewares.guards import MaintenanceMiddleware, AntiFloodMiddleware
from handlers import setup_routers


def create_bot() -> Bot:
    return Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.update.middleware(DatabaseMiddleware())
    dp.update.middleware(UserMiddleware())
    dp.update.middleware(MaintenanceMiddleware())
    dp.update.middleware(AntiFloodMiddleware())
    dp.include_router(setup_routers())
    return dp
