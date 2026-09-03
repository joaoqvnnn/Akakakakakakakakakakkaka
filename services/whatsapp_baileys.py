"""
Baileys API — texto, imagem e botões interativos.
Ajuste paths se sua API usar outros endpoints.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, List, Dict

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from services.settings_service import SettingsService

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("0"):
        digits = digits.lstrip("0")
    if len(digits) <= 11 and not digits.startswith("55"):
        digits = "55" + digits
    return digits


class WhatsAppBaileysService:
    @staticmethod
    async def _config(session: AsyncSession) -> dict:
        base = (await SettingsService.get(session, "baileys_api_url") or "").rstrip("/")
        key = await SettingsService.get(session, "baileys_api_key") or ""
        enabled = await SettingsService.get_bool(session, "baileys_enabled")
        return {"base": base, "key": key, "enabled": enabled}

    @staticmethod
    async def _headers(session: AsyncSession) -> dict:
        cfg = await WhatsAppBaileysService._config(session)
        headers = {"Content-Type": "application/json"}
        if cfg["key"]:
            headers["Authorization"] = f"Bearer {cfg['key']}"
            headers["X-API-Key"] = cfg["key"]
        return headers

    @staticmethod
    async def _post(session: AsyncSession, path: str, payload: dict) -> bool:
        cfg = await WhatsAppBaileysService._config(session)
        if not cfg["enabled"] or not cfg["base"]:
            logger.warning("Baileys OFF ou sem URL")
            return False
        url = f"{cfg['base']}{path}"
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                r = await client.post(
                    url,
                    json=payload,
                    headers=await WhatsAppBaileysService._headers(session),
                )
                if r.status_code >= 400:
                    logger.error("Baileys %s -> %s %s", path, r.status_code, r.text)
                    return False
                return True
        except Exception:
            logger.exception("Baileys POST %s failed", path)
            return False

    @staticmethod
    async def send_text(session: AsyncSession, phone: str, message: str) -> bool:
        return await WhatsAppBaileysService._post(
            session,
            "/send-message",
            {"number": normalize_phone(phone), "message": message},
        )

    @staticmethod
    async def send_image_with_caption(
        session: AsyncSession,
        phone: str,
        caption: str,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
    ) -> bool:
        payload: Dict[str, Any] = {
            "number": normalize_phone(phone),
            "caption": caption,
        }
        if image_url:
            payload["image"] = image_url
            payload["url"] = image_url
        if image_base64:
            payload["image"] = image_base64
            payload["base64"] = image_base64
        ok = await WhatsAppBaileysService._post(session, "/send-image", payload)
        if not ok:
            return await WhatsAppBaileysService.send_text(session, phone, caption)
        return True

    @staticmethod
    async def send_buttons(
        session: AsyncSession,
        phone: str,
        text: str,
        buttons: List[Dict[str, str]],
        footer: str = "Larizinha Store",
    ) -> bool:
        """
        buttons: [{"id": "confirm_order:123", "text": "Confirmar"}]
        Endpoint comum em wrappers Baileys: /send-button ou /send-buttons
        """
        payload = {
            "number": normalize_phone(phone),
            "message": text,
            "text": text,
            "footer": footer,
            "buttons": [
                {"id": b["id"], "text": b["text"], "buttonId": b["id"], "buttonText": {"displayText": b["text"]}}
                for b in buttons
            ],
        }
        ok = await WhatsAppBaileysService._post(session, "/send-button", payload)
        if not ok:
            ok = await WhatsAppBaileysService._post(session, "/send-buttons", payload)
        if not ok:
            # fallback texto
            lines = text + "\n\n"
            for b in buttons:
                lines += f"→ {b['text']}\n"
            lines += "\nResponda CONFIRMAR para continuar."
            return await WhatsAppBaileysService.send_text(session, phone, lines)
        return True

    @staticmethod
    async def send_delivery_preview(
        session: AsyncSession,
        phone: str,
        product_name: str,
        price: str,
        date_str: str,
        payment_method: str,
        order_id: str,
        store_name: str,
        image_url: Optional[str] = None,
        extra_caption: Optional[str] = None,
        order_db_id: Optional[int] = None,
    ) -> bool:
        caption = extra_caption or (
            f"✅ *Compra — {store_name}*\n\n"
            f"🎬 *{product_name}*\n"
            f"💰 Valor: R$ {price}\n"
            f"📅 {date_str}\n"
            f"💳 {payment_method}\n"
            f"🆔 Pedido: {order_id}\n\n"
            f"Toque em *Confirmar* para liberar o acesso."
        )
        if image_url:
            await WhatsAppBaileysService.send_image_with_caption(
                session, phone, caption, image_url=image_url
            )
        else:
            await WhatsAppBaileysService.send_text(session, phone, caption)

        btn_id = f"confirm_order:{order_db_id}" if order_db_id else "confirm_order"
        return await WhatsAppBaileysService.send_buttons(
            session,
            phone,
            "🔐 Confirme para receber login e senha do produto.",
            buttons=[{"id": btn_id, "text": "✅ Confirmar"}],
        )

    @staticmethod
    async def ask_release_password(
        session: AsyncSession, phone: str, order_db_id: int
    ) -> bool:
        return await WhatsAppBaileysService.send_text(
            session,
            phone,
            "🔐 *Verificação de segurança*\n\n"
            "Digite agora a *senha de liberação* cadastrada.\n"
            "Senha errada = dados do produto *não* serão enviados.\n\n"
            f"(Pedido #{order_db_id})",
        )

    @staticmethod
    async def send_credentials(
        session: AsyncSession,
        phone: str,
        product_name: str,
        delivery_content: str,
        activation_help: str = "",
    ) -> bool:
        msg = (
            f"🔓 *Acesso liberado*\n\n"
            f"Produto: *{product_name}*\n\n"
            f"*Login / dados:*\n"
            f"```{delivery_content}```\n\n"
        )
        if activation_help:
            msg += f"*Como ativar:*\n{activation_help}\n\n"
        msg += "Guarde com segurança."
        return await WhatsAppBaileysService.send_text(session, phone, msg)
