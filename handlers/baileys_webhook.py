import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Order, Product
from services.settings_service import SettingsService
from services.messages import MessageService
from services.whatsapp_baileys import WhatsAppBaileysService, normalize_phone
from services.whatsapp_order_flow import WhatsAppOrderFlow
from services.order_secure_link import OrderSecureService
from database.models import User

logger = logging.getLogger(__name__)


def _extract_phone(data: Dict[str, Any]) -> str:
    for k in ("number", "phone", "from", "remoteJid", "participant"):
        v = data.get(k)
        if v:
            return normalize_phone(str(v).split("@")[0])
    msg = data.get("message") or data.get("data") or {}
    if isinstance(msg, dict):
        for k in ("number", "phone", "from", "remoteJid"):
            v = msg.get(k)
            if v:
                return normalize_phone(str(v).split("@")[0])
    return ""


def _extract_text(data: Dict[str, Any]) -> str:
    if data.get("text"):
        return str(data["text"]).strip()
    if data.get("body"):
        return str(data["body"]).strip()
    msg = data.get("message") or {}
    if isinstance(msg, dict):
        if msg.get("conversation"):
            return str(msg["conversation"]).strip()
        ext = msg.get("extendedTextMessage") or {}
        if ext.get("text"):
            return str(ext["text"]).strip()
        btn = msg.get("buttonsResponseMessage") or msg.get("listResponseMessage") or {}
        if btn.get("selectedButtonId"):
            return str(btn["selectedButtonId"]).strip()
        if btn.get("selectedDisplayText"):
            return str(btn["selectedDisplayText"]).strip()
        if btn.get("selectedRowId"):
            return str(btn["selectedRowId"]).strip()
    if data.get("buttonId"):
        return str(data["buttonId"]).strip()
    if data.get("selectedButtonId"):
        return str(data["selectedButtonId"]).strip()
    return ""


async def handle_baileys_incoming(session: AsyncSession, data: Dict[str, Any]) -> dict:
    phone = _extract_phone(data)
    text = _extract_text(data)
    if not phone:
        return {"ok": False, "error": "phone missing"}

    lower = text.lower().strip()
    order_id: Optional[int] = None

    if text.startswith("confirm_order:"):
        try:
            order_id = int(text.split(":")[1])
        except Exception:
            order_id = None

    if order_id:
        order = await session.get(Order, order_id)
        if not order:
            await WhatsAppBaileysService.send_text(session, phone, "❌ Pedido nao encontrado.")
            return {"ok": True, "action": "order_not_found"}

        pwd_on = await SettingsService.get_bool(session, "delivery_password_enabled")
        if pwd_on:
            WhatsAppOrderFlow.set_pending(phone, order.id, order.user_id)
            await WhatsAppBaileysService.ask_release_password(session, phone, order.id)
            return {"ok": True, "action": "ask_password"}

        await _release(session, order, phone)
        return {"ok": True, "action": "released"}

    pending = WhatsAppOrderFlow.get_pending(phone)
    if pending and text and not text.startswith("confirm_order"):
        expected = await SettingsService.get(session, "delivery_password") or "1234"
        user = await session.get(User, pending.user_id)
        ok_pwd = False
        if user:
            ok_pwd = OrderSecureService.check_user_password(user, text.strip(), expected)
        if not ok_pwd and text.strip() != expected:
            await WhatsAppBaileysService.send_text(
                session,
                phone,
                "❌ Senha incorreta. Os dados do produto *nao* foram enviados.",
            )
            WhatsAppOrderFlow.pop_pending(phone)
            return {"ok": True, "action": "wrong_password"}

        order = await session.get(Order, pending.order_id)
        WhatsAppOrderFlow.pop_pending(phone)
        if not order:
            await WhatsAppBaileysService.send_text(session, phone, "❌ Pedido nao encontrado.")
            return {"ok": True, "action": "order_missing"}
        await _release(session, order, phone)
        return {"ok": True, "action": "released_after_password"}

    if lower in ("confirmar", "✅ confirmar", "confirm"):
        result = await session.execute(
            select(Order).order_by(Order.id.desc()).limit(30)
        )
        for order in result.scalars().all():
            if order.delivery_whatsapp and normalize_phone(order.delivery_whatsapp) == phone:
                pwd_on = await SettingsService.get_bool(session, "delivery_password_enabled")
                if pwd_on:
                    WhatsAppOrderFlow.set_pending(phone, order.id, order.user_id)
                    await WhatsAppBaileysService.ask_release_password(session, phone, order.id)
                    return {"ok": True, "action": "ask_password_text"}
                await _release(session, order, phone)
                return {"ok": True, "action": "released_text"}

    return {"ok": True, "action": "ignored"}


async def _release(session: AsyncSession, order: Order, phone: str) -> None:
    product = await session.get(Product, order.product_id)
    name = product.name if product else "Produto"
    activation = (await MessageService.get_rendered(session, "delivery_activation_help"))["content"]
    await WhatsAppBaileysService.send_credentials(
        session, phone, name, order.delivery_content or "—", activation_help=activation
    )
