from aiogram import Router


def _include(root: Router, path: str) -> None:
    try:
        mod = __import__(path, fromlist=["router"])
        root.include_router(mod.router)
        print(f"[OK] loaded {path}")
    except Exception as e:
        print(f"[WARN] skip {path}: {e}")


def setup_routers() -> Router:
    root = Router()

    for path in (
        "handlers.client.start",
        "handlers.client.catalog",
        "handlers.client.purchase",
        "handlers.client.wallet",
        "handlers.client.profile",
        "handlers.client.affiliates",
        "handlers.client.extras",
        "handlers.client.alerts",
        "handlers.client.search",
        "handlers.client.delivery",
        "handlers.client.withdraw_pix",
        "handlers.client.security",
        "handlers.client.points",
        "handlers.client.ai_chat",
    ):
        _include(root, path)

    try:
        from handlers.admin import setup_admin_routers
        root.include_router(setup_admin_routers())
        print("[OK] admin routers")
    except Exception as e:
        print(f"[WARN] admin routers: {e}")

    return root
