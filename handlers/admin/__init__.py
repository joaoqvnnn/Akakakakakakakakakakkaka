from aiogram import Router

from handlers.admin.panel import router as panel_router
from handlers.admin.config import router as config_router
from handlers.admin.logins import router as logins_router
from handlers.admin.users import router as users_router
from handlers.admin.messages import router as messages_router
from handlers.admin.giftcards import router as giftcards_router
from handlers.admin.payments import router as payments_router
from handlers.admin.broadcast import router as broadcast_router
from handlers.admin.smtp import router as smtp_router
from handlers.admin.buttons import router as buttons_router
from handlers.admin.products_media import router as products_media_router
from handlers.admin.welcome_media import router as welcome_media_router
from handlers.admin.withdraws import router as withdraws_router
from handlers.admin.web_password import router as web_password_router
from handlers.admin.categories import router as categories_router
from handlers.admin.antiflood_cfg import router as antiflood_router
from handlers.admin.search_images import router as search_images_router


def setup_admin_routers() -> Router:
    router = Router()
    for r in (
        panel_router,
        config_router,
        logins_router,
        users_router,
        messages_router,
        giftcards_router,
        payments_router,
        broadcast_router,
        smtp_router,
        buttons_router,
        products_media_router,
        welcome_media_router,
        withdraws_router,
        web_password_router,
        categories_router,
        antiflood_router,
        search_images_router,
    ):
        router.include_router(r)
    return router
