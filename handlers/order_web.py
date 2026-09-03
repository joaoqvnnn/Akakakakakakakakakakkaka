from pathlib import Path

from aiohttp import web

from config import settings
from database.session import AsyncSessionLocal
from database.models import Product, User
from services.order_secure_link import OrderSecureService
from services.order_pdf import build_order_pdf
from services.messages import MessageService
from services.settings_service import SettingsService

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


async def page_pedido(request: web.Request) -> web.Response:
    path = WEB_DIR / "pedido.html"
    if not path.exists():
        return web.Response(text="pedido.html nao encontrado", status=404)
    return web.Response(text=path.read_text(encoding="utf-8"), content_type="text/html")


async def api_pedido_meta(request: web.Request) -> web.Response:
    uuid = request.match_info["uuid"]
    token = request.query.get("t", "")
    async with AsyncSessionLocal() as session:
        order = await OrderSecureService.get_order(session, uuid, token)
        if not order:
            return web.json_response({"ok": False, "error": "Link invalido"}, status=403)
        product = await session.get(Product, order.product_id)
        return web.json_response(
            {
                "ok": True,
                "product_name": product.name if product else "Produto",
                "price": f"{order.total_price:.2f}",
                "date": order.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "expires": order.expires_at.strftime("%d/%m/%Y") if order.expires_at else "—",
                "payment_method": order.payment_method.value,
            }
        )


async def api_pedido_unlock(request: web.Request) -> web.Response:
    uuid = request.match_info["uuid"]
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "JSON invalido"}, status=400)

    token = data.get("t") or request.query.get("t", "")
    password = (data.get("password") or "").strip()

    async with AsyncSessionLocal() as session:
        order = await OrderSecureService.get_order(session, uuid, token)
        if not order:
            return web.json_response({"ok": False, "error": "Link invalido"}, status=403)

        user = await session.get(User, order.user_id)
        fallback = await SettingsService.get(session, "delivery_password") or "1234"
        if not user or not OrderSecureService.check_user_password(user, password, fallback):
            return web.json_response({"ok": False, "error": "Senha incorreta"}, status=401)

        product = await session.get(Product, order.product_id)
        store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
        activation = (await MessageService.get_rendered(session, "delivery_activation_help"))["content"]

        pdf = build_order_pdf(
            store_name=store,
            product_name=product.name if product else "Produto",
            order_uuid=order.uuid,
            price=f"{order.total_price:.2f}",
            date_str=order.created_at.strftime("%d/%m/%Y %H:%M:%S"),
            expires_str=order.expires_at.strftime("%d/%m/%Y") if order.expires_at else "—",
            payment_method=order.payment_method.value,
            delivery_content=order.delivery_content or "—",
            activation_help=activation,
        )
        return web.Response(
            body=pdf,
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": f'attachment; filename="pedido-{uuid}.pdf"',
            },
        )


def setup_order_web_routes(app: web.Application) -> None:
    app.router.add_get("/pedido/{uuid}", page_pedido)
    app.router.add_get("/api/pedido/{uuid}", api_pedido_meta)
    app.router.add_post("/api/pedido/{uuid}/unlock", api_pedido_unlock)
