import time
from typing import Any, Awaitable, Callable, Dict, DefaultDict
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database.session import AsyncSessionLocal
from services.settings_service import SettingsService
from services.messages import MessageService


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session = data.get("session")
        db_user = data.get("db_user")
        if session is not None:
            try:
                from config import settings

                is_admin = False
                if db_user:
                    is_admin = bool(db_user.is_admin) or (
                        db_user.id in settings.ADMIN_IDS
                    )
                if not is_admin:
                    on = await SettingsService.get_bool(session, "maintenance_mode")
                    if on:
                        msg = await SettingsService.get(
                            session, "maintenance_message"
                        )
                        text = msg or "🔧 Sistema em manutenção."
                        if isinstance(event, Message):
                            await event.answer(text)
                            return None
                        if isinstance(event, CallbackQuery):
                            await event.answer(text[:180], show_alert=True)
                            return None
            except Exception:
                pass
        return await handler(event, data)


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self):
        self._commands: DefaultDict[int, list] = defaultdict(list)
        self._blocked_until: Dict[int, float] = {}

    def _clean(self, store: list, user_id: int, window: float) -> list:
        now = time.time()
        return [t for t in store if now - t < window]

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            if isinstance(event, Message) and event.from_user:
                user = event.from_user
            elif isinstance(event, CallbackQuery) and event.from_user:
                user = event.from_user
        if user is None:
            return await handler(event, data)

        user_id = user.id
        now = time.time()

        if user_id in self._blocked_until and now < self._blocked_until[user_id]:
            remain = int(self._blocked_until[user_id] - now)
            text = f"⏳ Aguarde {remain}s para usar o bot novamente."
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return None

        session = data.get("session")
        max_commands = 8
        window = 10
        block_min = 10
        if session is not None:
            try:
                max_commands = await SettingsService.get_int(
                    session, "flood_max_commands"
                ) or 8
                window = await SettingsService.get_int(
                    session, "flood_window_seconds"
                ) or 10
                block_min = await SettingsService.get_int(
                    session, "flood_block_minutes"
                ) or 10
            except Exception:
                pass

        if isinstance(event, Message) and event.text and event.text.startswith("/"):
            ts = self._clean(self._commands[user_id], user_id, float(window))
            ts.append(now)
            self._commands[user_id] = ts
            if len(ts) >= max_commands:
                self._blocked_until[user_id] = now + block_min * 60
                warn = "⏳ Você está enviando comandos muito rápido. Aguarde alguns minutos."
                if session is not None:
                    try:
                        tpl = await MessageService.get_rendered(
                            session, "flood_warning"
                        )
                        warn = tpl["content"]
                    except Exception:
                        pass
                await event.answer(warn)
                return None

        return await handler(event, data)
