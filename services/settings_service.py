from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SystemSetting


DEFAULTS = {
    "store_name": "Larizinha Store",
    "support_link": "https://t.me/suporte",
    "separator": "===",
    "logs_chat_id": "",
    "maintenance_mode": "0",
    "maintenance_message": "🔧 Bot em manutenção no momento. Tente mais tarde.",
    "mp_access_token": "",
    "pix_min": "4",
    "pix_max": "5000",
    "pix_expiration_minutes": "10",
    "bonus_percent": "0",
    "bonus_min_value": "0",
    "register_bonus": "0",
    "affiliate_enabled": "1",
    "affiliate_commission_percent": "20",
    "affiliate_min_withdraw": "20",
    "points_per_recharge": "1",
    "points_min_convert": "500",
    "points_multiplier": "0.01",
    "flood_max_commands": "8",
    "flood_window_seconds": "10",
    "flood_block_minutes": "10",
    "baileys_enabled": "0",
    "baileys_api_url": "",
    "baileys_api_key": "",
    "delivery_password_enabled": "1",
    "delivery_password": "1234",
    "delivery_whatsapp_image_url": "",
    "smtp_enabled": "0",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from": "",
    "smtp_use_tls": "1",
    "web_withdraw_password": "Larizinha@2026",
    "welcome_image_file_id": "",
}


class SettingsService:
    @staticmethod
    async def ensure_defaults(session: AsyncSession) -> None:
        for key, value in DEFAULTS.items():
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key == key)
            )
            if result.scalar_one_or_none() is None:
                session.add(SystemSetting(key=key, value=str(value)))
        await session.flush()

    @staticmethod
    async def get(
        session: AsyncSession, key: str, default: Optional[str] = None
    ) -> Optional[str]:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row.value
        if default is not None:
            return default
        return DEFAULTS.get(key)

    @staticmethod
    async def get_bool(session: AsyncSession, key: str) -> bool:
        val = await SettingsService.get(session, key)
        return str(val).lower() in ("1", "true", "yes", "on")

    @staticmethod
    async def get_int(session: AsyncSession, key: str) -> int:
        val = await SettingsService.get(session, key) or "0"
        try:
            return int(float(str(val).replace(",", ".")))
        except Exception:
            return 0

    @staticmethod
    async def get_float(session: AsyncSession, key: str) -> float:
        val = await SettingsService.get(session, key) or "0"
        try:
            return float(str(val).replace(",", "."))
        except Exception:
            return 0.0

    @staticmethod
    async def get_decimal(session: AsyncSession, key: str) -> Decimal:
        return Decimal(str(await SettingsService.get_float(session, key)))

    @staticmethod
    async def set(
        session: AsyncSession,
        key: str,
        value: str,
        admin_id: Optional[int] = None,
    ) -> None:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = str(value)
            row.updated_by = admin_id
        else:
            session.add(
                SystemSetting(key=key, value=str(value), updated_by=admin_id)
            )
        await session.flush()
