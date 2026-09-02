from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, UserStatus, TransactionType
from services.balance import BalanceService
from services.settings_service import SettingsService


class UserMiddleware(BaseMiddleware):
    """
    Garante usuário no banco, atualiza dados, captura afiliado do /start REF,
    aplica bônus de registro, bloqueia banidos.
    Injeta data['db_user'].
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        session: AsyncSession | None = data.get("session")

        if not tg_user or not session:
            return await handler(event, data)

        result = await session.execute(select(User).where(User.id == tg_user.id))
        db_user = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if db_user is None:
            referred_by = None
            if isinstance(event, Message) and event.text and event.text.startswith("/start "):
                parts = event.text.split(maxsplit=1)
                if len(parts) == 2 and parts[1].isdigit():
                    ref_id = int(parts[1])
                    if ref_id != tg_user.id:
                        ref = await session.get(User, ref_id)
                        if ref:
                            referred_by = ref_id

            is_owner = tg_user.id in settings.ADMIN_IDS
            db_user = User(
                id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language_code=tg_user.language_code,
                referred_by=referred_by,
                is_admin=is_owner,
                admin_role="owner" if is_owner else None,
                last_activity=now,
            )
            session.add(db_user)

            if referred_by:
                ref_user = await session.get(User, referred_by)
                if ref_user:
                    ref_user.total_referrals += 1

            await session.flush()

            # Bônus de registro (configurável no admin)
            try:
                bonus = await SettingsService.get_float(session, "registration_bonus")
                if bonus > 0:
                    from decimal import Decimal

                    await BalanceService.add_balance(
                        session=session,
                        user_id=db_user.id,
                        amount=Decimal(str(bonus)),
                        tx_type=TransactionType.REGISTRATION_BONUS,
                        description="Bônus de boas-vindas",
                    )
            except Exception:
                pass
        else:
            db_user.username = tg_user.username
            db_user.first_name = tg_user.first_name
            db_user.last_name = tg_user.last_name
            db_user.language_code = tg_user.language_code
            db_user.last_activity = now

            if tg_user.id in settings.ADMIN_IDS and not db_user.is_admin:
                db_user.is_admin = True
                db_user.admin_role = "owner"

        if db_user.status in (UserStatus.BLOCKED, UserStatus.BANNED):
            if isinstance(event, Message):
                await event.answer("🚫 Você está bloqueado e não pode usar este bot.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Você está bloqueado.", show_alert=True)
            return

        data["db_user"] = db_user
        return await handler(event, data)
