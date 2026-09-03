import logging
from aiohttp import web

from config import settings
from database.session import AsyncSessionLocal
from database.models import PaymentStatus
from services.payment import PaymentService
from web_routes import setup_web_routes

logger = logging.getLogger(__name__)
payment_service = PaymentService()
_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


async def mercadopago_webhook(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        data = dict(request.query)
    logger.info("Webhook MP: %s", data)

    topic = data.get("type") or data.get("topic") or data.get("action", "")
    resource_id = None
    if isinstance(data.get("data"), dict):
        resource_id = data["data"].get("id")
    elif "id" in data:
        resource_id = data.get("id")
    if not resource_id:
        resource_id = request.query.get("id") or request.query.get("data.id")
    if not resource_id:
        return web.Response(text="ok", status=200)
    if topic and "payment" not in str(topic).lower():
        return web.Response(text="ignored", status=200)

    async with AsyncSessionLocal() as session:
        try:
            payment = await payment_service.process_webhook(session, str(resource_id))
            await session.commit()
            if payment and payment.status == PaymentStatus.APPROVED and _bot:
                from utils.notify import notify_user_payment_approved
                await notify_user_payment_approved(_bot, payment)
        except Exception:
            await session.rollback()
            logger.exception("Erro webhook MP")
    return web.Response(text="ok", status=200)


async def health_check(request: web.Request) -> web.Response:
    return web.Response(text="ok", status=200)


def create_webhook_app() -> web.Application:
    app = web.Application()
    app.router.add_post(settings.WEBHOOK_PATH, mercadopago_webhook)
    app.router.add_get(settings.WEBHOOK_PATH, mercadopago_webhook)
    app.router.add_get("/health", health_check)
    setup_web_routes(app)
    return app


async def start_webhook_server():
    app = create_webhook_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEBHOOK_HOST, settings.WEBHOOK_PORT)
    await site.start()
    logger.info(
        "HTTP %s:%s | MP + /webhook/baileys + site saque",
        settings.WEBHOOK_HOST,
        settings.WEBHOOK_PORT,
    )
    return runner
