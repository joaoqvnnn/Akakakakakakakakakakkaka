from handlers.admin.buttons import router as buttons_router
from handlers.admin.products_media import router as products_media_router

# dentro de setup_admin_routers():
router.include_router(buttons_router)
router.include_router(products_media_router)
