from aiogram import Router


def setup_admin_routers() -> Router:
    router = Router()

    modules = [
        "handlers.admin.panel",
        "handlers.admin.config",
        "handlers.admin.logins",
        "handlers.admin.users",
        "handlers.admin.messages",
        "handlers.admin.giftcards",
        "handlers.admin.payments",
        "handlers.admin.broadcast",
        "handlers.admin.smtp",
        "handlers.admin.buttons",
        "handlers.admin.products_media",
        "handlers.admin.welcome_media",
        "handlers.admin.withdraws",
        "handlers.admin.web_password",
        "handlers.admin.categories",
        "handlers.admin.antiflood_cfg",
        "handlers.admin.search_images",
    ]

    for path in modules:
        try:
            mod = __import__(path, fromlist=["router"])
            router.include_router(mod.router)
        except Exception as e:
            print(f"[WARN] admin router skip {path}: {e}")

    return router
