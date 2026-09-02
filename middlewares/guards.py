import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import settings
from database.models import User
from services.settings_service import SettingsService


class MaintenanceMiddleware(BaseMiddleware):
    """Bloqueia clientes se manutenção estiver ativa (admins passam)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session = data.get("session")
        db_user: User | None = data.get("db_user")
        tg_user = data.get("event_from_user")

        maintenance = settings.MAINTENANCE_MODE if hasattr(settings, "MAINTENANCE_MODE") else False
        if session:
            try:
                maintenance = await SettingsService.get_bool(session, "maintenance_mode")
            except Exception:
                pass

        if not maintenance:
            return await handler(event, data)

        if db_user and db_user.is_admin:
            return await handler(event, data)
        if tg_user and tg_user.id in settings.ADMIN_IDS:
            return await handler(event, data)

        msg = "🔧 Nosso sistema está temporariamente em manutenção.\nVoltaremos em breve."
        if session:
            try:
                msg = await SettingsService.get(session, "maintenance_message", msg)
            except Exception:
                pass

        if isinstance(event, Message):
            await event.answer(msg)
        elif isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=True)
        return


class AntiFloodMiddleware(BaseMiddleware):
    """
    Anti-flood em memória (por processo).
    Limites podem vir do banco (flood_*), com fallback no código.
    """

    def __init__(self) -> None:
        self._commands: Dict[int, list[float]] = {}
        self._callbacks: Dict[int, list[float]] = {}
        self._pix: Dict[int, list[float]] = {}
        self._gift: Dict[int, list[float]] = {}

    def _clean(self, store: Dict[int, list[float]], user_id: int, window: float) -> list[float]:
        now = time.time()
        timestamps = [t for t in store.get(user_id, []) if now - t < window]
        store[user_id] = timestamps
        return timestamps

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if not tg_user:
            return await handler(event, data)

        user_id = tg_user.id
        now = time.time()

        max_commands = 8
        window = 10.0
        session = data.get("session")
        if session:
            try:
                max_commands = await SettingsService.get_int(session, "flood_max_commands") or 8
                window = float(await SettingsService.get_int(session, "flood_window_seconds") or 10)
            except Exception:
                pass

        if isinstance(event, Message) and event.text and event.text.startswith("/"):
            ts = self._clean(self._commands, user_id, window)
            if len(ts) >= max_commands:
                await event.answer("⏳ Você está enviando comandos muito rápido. Aguarde alguns segundos.")
                return
            self._commands.setdefault(user_id, []).append(now)

        if isinstance(event, CallbackQuery):
            ts = self._clean(self._callbacks, user_id, 1.0)
            if len(ts) >= 5:
                await event.answer("⏳ Calma! Clique mais devagar.", show_alert=False)
                return
            self._callbacks.setdefault(user_id, []).append(now)

            if event.data and event.data.startswith("pix"):
                pix_ts = self._clean(self._pix, user_id, 3600)
                if len(pix_ts) >= 15:
                    await event.answer("❌ Limite de PIX por hora atingido. Tente mais tarde.", show_alert=True)
                    return
                self._pix.setdefault(user_id, []).append(now)

            if event.data and event.data.startswith("gift"):
                gift_ts = self._clean(self._gift, user_id, 3600)
                if len(gift_ts) >= 10:
                    await event.answer("❌ Muitas tentativas de Gift Card. Aguarde.", show_alert=True)
                    return
                self._gift.setdefault(user_id, []).append(now)

        return await handler(event, data)
