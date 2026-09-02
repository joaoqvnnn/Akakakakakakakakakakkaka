from aiogram import Router

from handlers.client.start import router as start_router
from handlers.client.catalog import router as catalog_router
from handlers.client.purchase import router as purchase_router
from handlers.client.wallet import router as wallet_router
from handlers.client.profile import router as profile_router
from handlers.client.affiliates import router as affiliates_router
from handlers.client.extras import router as extras_router
from handlers.client.alerts import router as alerts_router
from handlers.client.search import router as search_router
from handlers.client.delivery import router as delivery_router
from handlers.admin import setup_admin_routers


def setup_routers() -> Router:
    root = Router()

    root.include_router(start_router)
    root.include_router(catalog_router)
    root.include_router(purchase_router)
    root.include_router(wallet_router)
    root.include_router(profile_router)
    root.include_router(affiliates_router)
    root.include_router(extras_router)
    root.include_router(alerts_router)
    root.include_router(search_router)
    root.include_router(delivery_router)

    root.include_router(setup_admin_routers())

    return root
