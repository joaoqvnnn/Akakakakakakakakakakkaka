from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select

from config import settings
from database.models import User
from services.settings_service import SettingsService
from services.balance import BalanceService
from database.models import TransactionType


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session = data.get("session")
        tg_user = data.get("event_from_user")

        if tg_user is None:
            if isinstance(event, Message) and event.from_user:
                tg_user = event.from_user
            elif isinstance(event, CallbackQuery) and event.from_user:
                tg_user = event.from_user

        if session is None or tg_user is None:
            return await handler(event, data)

        result = await session.execute(select(User).where(User.id == tg_user.id))
        user = result.scalar_one_or_none()
        is_new = False

        if user is None:
            is_new = True
            user = User(
                id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language_code=tg_user.language_code,
            )
            if tg_user.id in getattr(settings, "ADMIN_IDS", []):
                user.is_admin = True
            session.add(user)
            await session.flush()

            try:
                bonus = await SettingsService.get_float(session, "register_bonus")
                if bonus and bonus > 0:
                    await BalanceService.add_balance(
                        session,
                        user.id,
                        bonus,
                        TransactionType.ADMIN_ADD,
                        description="Bônus de registro",
                    )
            except Exception:
                pass
        else:
            user.username = tg_user.username
            user.first_name = tg_user.first_name
            user.last_name = tg_user.last_name
            if tg_user.id in getattr(settings, "ADMIN_IDS", []):
                user.is_admin = True

        if user.is_blocked:
            if isinstance(event, Message):
                await event.answer("🚫 Você está bloqueado neste bot.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Você está bloqueado.", show_alert=True)
            return None

        data["db_user"] = user
        data["is_new_user"] = is_new
        return await handler(event, data)
