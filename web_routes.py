import logging
from pathlib import Path

from aiohttp import web

from database.session import AsyncSessionLocal
from services.withdraw_web import WithdrawWebService
from handlers.baileys_webhook import handle_baileys_incoming
from handlers.order_web import setup_order_web_routes

logger = logging.getLogger(__name__)
WEB_DIR = Path(__file__).resolve().parent / "web"


def _read_html(name: str) -> str:
    path = WEB_DIR / name
    if not path.exists():
        return f"<h1>Arquivo {name} não encontrado</h1>"
    return path.read_text(encoding="utf-8")


async def page_login(request: web.Request) -> web.Response:
    return web.Response(text=_read_html("login.html"), content_type="text/html")


async def page_saque_form(request: web.Request) -> web.Response:
    return web.Response(text=_read_html("saque.html"), content_type="text/html")


async def page_saque_uuid(request: web.Request) -> web.Response:
    return web.Response(text=_read_html("login.html"), content_type="text/html")


async def page_saque_uuid_form(request: web.Request) -> web.Response:
    return web.Response(text=_read_html("saque.html"), content_type="text/html")


async def page_historico(request: web.Request) -> web.Response:
    return web.Response(text=_read_html("historico.html"), content_type="text/html")


async def page_termos(request: web.Request) -> web.Response:
    path = WEB_DIR / "termos.html"
    if path.exists():
        return web.Response(text=path.read_text(encoding="utf-8"), content_type="text/html")
    return web.Response(text=_read_html("historico.html"), content_type="text/html")


async def api_check_password(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "JSON inválido"}, status=400)
    password = (data.get("password") or "").strip()
    async with AsyncSessionLocal() as session:
        ok = await WithdrawWebService.check_web_password(session, password)
        await session.commit()
    if not ok:
        return web.json_response({"ok": False, "error": "Senha incorreta"}, status=401)
    return web.json_response({"ok": True})


async def api_saque_info(request: web.Request) -> web.Response:
    uuid = request.match_info.get("uuid", "")
    async with AsyncSessionLocal() as session:
        w = await WithdrawWebService.get_by_uuid(session, uuid)
        if not w:
            return web.json_response({"ok": False, "error": "Saque não encontrado"}, status=404)
        return web.json_response(
            {
                "ok": True,
                "uuid": w.uuid,
                "amount": float(w.amount),
                "status": w.status.value,
                "payment_method": w.payment_method,
                "user_id": w.user_id,
            }
        )


async def api_saque_submit(request: web.Request) -> web.Response:
    uuid = request.match_info.get("uuid", "")
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "JSON inválido"}, status=400)
    async with AsyncSessionLocal() as session:
        try:
            w = await WithdrawWebService.save_bank_data(
                session,
                uuid,
                bank_code=str(data.get("bank_code", "")),
                bank_name=str(data.get("bank_name", "")),
                agency=str(data.get("agency", "")),
                agency_digit=str(data.get("agency_digit", "")),
                account=str(data.get("account", "")),
                account_digit=str(data.get("account_digit", "")),
                account_type=str(data.get("account_type", "checking")),
                holder_name=str(data.get("holder_name", "")),
                holder_document=str(data.get("holder_document", "")),
                withdraw_password=str(data.get("withdraw_password", "")),
            )
            await session.commit()
            return web.json_response(
                {
                    "ok": True,
                    "message": "Dados bancários salvos. Aguarde o processamento.",
                    "uuid": w.uuid,
                    "status": w.status.value,
                }
            )
        except ValueError as e:
            await session.rollback()
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        except Exception:
            await session.rollback()
            logger.exception("Erro saque")
            return web.json_response({"ok": False, "error": "Erro interno"}, status=500)


async def api_historico(request: web.Request) -> web.Response:
    try:
        user_id = int(request.query.get("user_id", "0"))
    except ValueError:
        return web.json_response({"ok": False, "error": "user_id inválido"}, status=400)
    async with AsyncSessionLocal() as session:
        items = await WithdrawWebService.list_user_withdraws(session, user_id)
        return web.json_response(
            {
                "ok": True,
                "items": [
                    {
                        "uuid": w.uuid,
                        "amount": float(w.amount),
                        "status": w.status.value,
                        "method": w.payment_method,
                        "created_at": w.created_at.isoformat() if w.created_at else None,
                    }
                    for w in items
                ],
            }
        )


async def baileys_webhook(request: web.Request) -> web.Response:
    """
    Configure sua API Baileys para POST aqui:
    https://seu-dominio/webhook/baileys
    """
    try:
        data = await request.json()
    except Exception:
        data = dict(request.query)
    logger.info("Baileys webhook: %s", data)
    async with AsyncSessionLocal() as session:
        try:
            result = await handle_baileys_incoming(session, data)
            await session.commit()
            return web.json_response(result)
        except Exception:
            await session.rollback()
            logger.exception("Baileys webhook error")
            return web.json_response({"ok": False}, status=500)


def setup_web_routes(app: web.Application) -> None:
    app.router.add_get("/login", page_login)
    app.router.add_get("/saque/form", page_saque_form)
    app.router.add_get("/saque/{uuid}", page_saque_uuid)
    app.router.add_get("/saque/{uuid}/form", page_saque_uuid_form)
    app.router.add_get("/historico", page_historico)
    app.router.add_get("/termos", page_termos)

    app.router.add_post("/api/web-auth", api_check_password)
    app.router.add_get("/api/saque/{uuid}", api_saque_info)
    app.router.add_post("/api/saque/{uuid}", api_saque_submit)
    app.router.add_get("/api/historico", api_historico)

    app.router.add_post("/webhook/baileys", baileys_webhook)
    app.router.add_get("/webhook/baileys", baileys_webhook)

    static_path = WEB_DIR / "static"
    if static_path.exists():
        app.router.add_static("/static/", path=str(static_path), name="static")

    setup_order_web_routes(app)
