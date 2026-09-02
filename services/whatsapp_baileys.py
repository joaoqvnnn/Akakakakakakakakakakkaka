"""
Integração com API Baileys (WhatsApp).

Configure no admin / .env:
  BAILEYS_API_URL   ex: http://127.0.0.1:3000
  BAILEYS_API_KEY   (opcional)

Endpoints esperados (ajuste se sua API for diferente):
  POST {BAILEYS_API_URL}/send-message
  POST {BAILEYS_API_URL}/send-image
  POST {BAILEYS_API_URL}/send-button  (se existir)

Body JSON típico:
  { "number": "5544999999999", "message": "texto" }
  { "number": "...", "caption": "...", "image": "url ou base64" }
"""

from __future__ import annotations

import logging
from typing import Any, Optional

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
        base = (await SettingsService.get(session, "baileys_api_url")).rstrip("/")
        key = await SettingsService.get(session, "baileys_api_key")
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
    async def send_text(
        session: AsyncSession,
        phone: str,
        message: str,
    ) -> bool:
        cfg = await WhatsAppBaileysService._config(session)
        if not cfg["enabled"] or not cfg["base"]:
            logger.warning("Baileys desabilitado ou URL vazia")
            return False

        number = normalize_phone(phone)
        url = f"{cfg['base']}/send-message"
        payload: dict[str, Any] = {"number": number, "message": message}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    url,
                    json=payload,
                    headers=await WhatsAppBaileysService._headers(session),
                )
                if r.status_code >= 400:
                    logger.error("Baileys text error %s: %s", r.status_code, r.text)
                    return False
                return True
        except Exception:
            logger.exception("Baileys send_text failed")
            return False

    @staticmethod
    async def send_image_with_caption(
        session: AsyncSession,
        phone: str,
        caption: str,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
    ) -> bool:
        cfg = await WhatsAppBaileysService._config(session)
        if not cfg["enabled"] or not cfg["base"]:
            return False

        number = normalize_phone(phone)
        url = f"{cfg['base']}/send-image"
        payload: dict[str, Any] = {
            "number": number,
            "caption": caption,
        }
        if image_url:
            payload["image"] = image_url
            payload["url"] = image_url
        if image_base64:
            payload["image"] = image_base64
            payload["base64"] = image_base64

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                r = await client.post(
                    url,
                    json=payload,
                    headers=await WhatsAppBaileysService._headers(session),
                )
                if r.status_code >= 400:
                    # Fallback: só texto
                    logger.warning("Baileys image failed, fallback text: %s", r.text)
                    return await WhatsAppBaileysService.send_text(session, phone, caption)
                return True
        except Exception:
            logger.exception("Baileys send_image failed")
            return await WhatsAppBaileysService.send_text(session, phone, caption)

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
    ) -> bool:
        """
        Primeira mensagem no WhatsApp (sem login/senha).
        Cliente confirma no Telegram e digita a senha de liberação.
        """
        caption = extra_caption or (
            f"✅ *Compra — {store_name}*\n\n"
            f"🎬 *{product_name}*\n"
            f"💰 Valor: R$ {price}\n"
            f"📅 {date_str}\n"
            f"💳 {payment_method}\n"
            f"🆔 Pedido: {order_id}\n\n"
            f"Volte ao *Telegram* e confirme a entrega.\n"
            f"Se a verificação estiver ativa, digite sua senha de liberação."
        )
        if image_url:
            return await WhatsAppBaileysService.send_image_with_caption(
                session, phone, caption, image_url=image_url
            )
        return await WhatsAppBaileysService.send_text(session, phone, caption)

    @staticmethod
    async def send_credentials(
        session: AsyncSession,
        phone: str,
        product_name: str,
        delivery_content: str,
        activation_help: str = "",
    ) -> bool:
        """Só depois da senha correta (ou se verificação estiver OFF)."""
        msg = (
            f"🔓 *Acesso liberado*\n\n"
            f"Produto: *{product_name}*\n\n"
            f"*Login / dados:*\n"
            f"```{delivery_content}```\n\n"
        )
        if activation_help:
            msg += f"*Como ativar:*\n{activation_help}\n\n"
        msg += "Guarde essas informações com segurança."
        return await WhatsAppBaileysService.send_text(session, phone, msg)
