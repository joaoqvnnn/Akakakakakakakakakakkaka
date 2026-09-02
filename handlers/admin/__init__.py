from aiogram import Router

from handlers.admin.panel import router as panel_router
from handlers.admin.config import router as config_router
from handlers.admin.logins import router as logins_router
from handlers.admin.users import router as users_router
from handlers.admin.messages import router as messages_router
from handlers.admin.giftcards import router as giftcards_router
from handlers.admin.payments import router as payments_router
from handlers.admin.broadcast import router as broadcast_router


def setup_admin_routers() -> Router:
    router = Router()
    router.include_router(panel_router)
    router.include_router(config_router)
    router.include_router(logins_router)
    router.include_router(users_router)
    router.include_router(messages_router)
    router.include_router(giftcards_router)
    router.include_router(payments_router)
    router.include_router(broadcast_router)
    return router
