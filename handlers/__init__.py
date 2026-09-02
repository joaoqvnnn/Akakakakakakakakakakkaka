from handlers.admin.broadcast import router as broadcast_router
from handlers.client.withdraw_pix import router as withdraw_pix_router

# dentro de setup_routers, cliente:
root.include_router(withdraw_pix_router)

# e no setup_admin_routers (handlers/admin/__init__.py):
router.include_router(broadcast_router)
