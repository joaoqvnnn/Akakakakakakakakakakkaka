from typing import Any, Optional, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SystemSetting


DEFAULTS: Dict[str, Any] = {
    "store_name": "Larizinha Store",
    "support_link": "https://t.me/suporte",
    "logs_chat_id": "",
    "separator": "===",
    "maintenance_mode": "false",
    "maintenance_message": "🔧 Sistema em manutenção. Voltamos em breve.",
    "registration_bonus": "0.00",
    "mp_access_token": "",
    "pix_min": "4.00",
    "pix_max": "5000.00",
    "pix_expiration_minutes": "10",
    "bonus_percent": "10",
    "bonus_min_value": "10.00",
    "bonus_enabled": "true",
    "pix_auto_enabled": "true",
    "affiliate_enabled": "true",
    "affiliate_commission_percent": "20",
    "affiliate_min_withdraw": "20.00",
    "points_per_recharge": "1",
    "points_min_convert": "500",
    "points_multiplier": "0.01",
    "flood_block_minutes": "10",
    "flood_max_commands": "8",
    "flood_window_seconds": "10",
    "low_stock_threshold": "5",
    # Baileys / WhatsApp
    "baileys_enabled": "false",
    "baileys_api_url": "http://127.0.0.1:3000",
    "baileys_api_key": "",
    "delivery_password_enabled": "true",
    "delivery_password": "1234",
    "delivery_whatsapp_image_url": "",
    # SMTP e-mail
    "smtp_enabled": "false",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from": "",
    "smtp_use_tls": "true",
}


class SettingsService:
    @staticmethod
    async def get(session: AsyncSession, key: str, default: Any = None) -> str:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row.value
        if default is not None:
            return str(default)
        return str(DEFAULTS.get(key, ""))

    @staticmethod
    async def get_bool(session: AsyncSession, key: str) -> bool:
        val = await SettingsService.get(session, key)
        return str(val).lower() in ("1", "true", "yes", "on", "sim")

    @staticmethod
    async def get_float(session: AsyncSession, key: str) -> float:
        try:
            return float(await SettingsService.get(session, key) or 0)
        except ValueError:
            return 0.0

    @staticmethod
    async def get_int(session: AsyncSession, key: str) -> int:
        try:
            return int(float(await SettingsService.get(session, key) or 0))
        except ValueError:
            return 0

    @staticmethod
    async def set(
        session: AsyncSession,
        key: str,
        value: Any,
        admin_id: Optional[int] = None,
        description: str = "",
    ) -> SystemSetting:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        row = result.scalar_one_or_none()
        str_value = str(value)
        if row:
            row.value = str_value
            row.updated_by = admin_id
            if description:
                row.description = description
        else:
            row = SystemSetting(
                key=key,
                value=str_value,
                value_type="string",
                description=description or key,
                updated_by=admin_id,
            )
            session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def ensure_defaults(session: AsyncSession) -> None:
        for key, value in DEFAULTS.items():
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key == key)
            )
            if result.scalar_one_or_none() is None:
                session.add(
                    SystemSetting(
                        key=key,
                        value=str(value),
                        value_type="string",
                        description=key,
                    )
                )
        await session.flush()
