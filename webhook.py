import logging
from aiohttp import web

from config import settings
from database.session import AsyncSessionLocal
from database.models import PaymentStatus
from services.payment import PaymentService

logger = logging.getLogger(__name__)
payment_service = PaymentService()

_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


async def mercadopago_webhook(request: web.Request) -> web.Response:
    """Recebe notificação do Mercado Pago e credita saldo (idempotente)."""
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

    gateway_id = str(resource_id)

    async with AsyncSessionLocal() as session:
        try:
            payment = await payment_service.process_webhook(session, gateway_id)
            await session.commit()

            if payment and payment.status == PaymentStatus.APPROVED and _bot:
                from utils.notify import notify_user_payment_approved

                await notify_user_payment_approved(_bot, payment)
                logger.info(
                    "PIX aprovado user=%s amount=%s",
                    payment.user_id,
                    payment.amount,
                )
        except Exception:
            await session.rollback()
            logger.exception("Erro no webhook MP")

    return web.Response(text="ok", status=200)


async def health_check(request: web.Request) -> web.Response:
    return web.Response(text="ok", status=200)


async def withdraw_page(request: web.Request) -> web.Response:
    """
    Única página web do projeto: formulário de dados bancários/Pix do saque.
    URL: /saque/{uuid}
    (Lógica completa de gravação pode ser expandida depois.)
    """
    uuid = request.match_info.get("uuid", "")
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Saque afiliado</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 420px; margin: 2rem auto; padding: 0 1rem; }}
    input, select, button {{ width: 100%; padding: 0.6rem; margin: 0.4rem 0; box-sizing: border-box; }}
    button {{ background: #2481cc; color: #fff; border: 0; border-radius: 8px; font-weight: 600; }}
    h1 {{ font-size: 1.2rem; }}
  </style>
</head>
<body>
  <h1>Dados para saque</h1>
  <p>Ref: <code>{uuid}</code></p>
  <form method="post" action="/saque/{uuid}">
    <label>Método</label>
    <select name="method">
      <option value="pix">Pix</option>
      <option value="bank">Transferência bancária</option>
    </select>
    <label>Chave Pix (se Pix)</label>
    <input name="pix_key" placeholder="CPF, e-mail, telefone ou aleatória"/>
    <label>Banco</label>
    <input name="bank_name" placeholder="Nome do banco"/>
    <label>Agência</label>
    <input name="agency"/>
    <label>Conta</label>
    <input name="account"/>
    <label>Nome do titular</label>
    <input name="holder_name" required/>
    <label>Senha de saque</label>
    <input name="password" type="password" required/>
    <button type="submit">Enviar dados</button>
  </form>
  <p style="color:#666;font-size:0.85rem">Página exclusiva para saque de afiliado. O painel da loja continua só no Telegram.</p>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def withdraw_submit(request: web.Request) -> web.Response:
    uuid = request.match_info.get("uuid", "")
    data = await request.post()
    # Gravação completa no banco será ligada ao AffiliateWithdraw no próximo lote admin
    logger.info("Saque form uuid=%s data=%s", uuid, dict(data))
    return web.Response(
        text="<h1>Dados recebidos</h1><p>Seu saque será processado. Volte ao Telegram.</p>",
        content_type="text/html",
    )


def create_webhook_app() -> web.Application:
    app = web.Application()
    app.router.add_post(settings.WEBHOOK_PATH, mercadopago_webhook)
    app.router.add_get(settings.WEBHOOK_PATH, mercadopago_webhook)
    app.router.add_get("/health", health_check)
    app.router.add_get("/saque/{uuid}", withdraw_page)
    app.router.add_post("/saque/{uuid}", withdraw_submit)
    return app


async def start_webhook_server():
    app = create_webhook_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEBHOOK_HOST, settings.WEBHOOK_PORT)
    await site.start()
    logger.info(
        "HTTP em http://%s:%s (MP: %s | saque: /saque/{{uuid}})",
        settings.WEBHOOK_HOST,
        settings.WEBHOOK_PORT,
        settings.WEBHOOK_PATH,
    )
    return runner
