from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    GiftCard,
    GiftCardStatus,
    GiftCardRedemption,
    TransactionType,
)
from services.balance import BalanceService


class GiftCardService:
    @staticmethod
    async def create(
        session: AsyncSession,
        code: str,
        value: Decimal,
        admin_id: Optional[int] = None,
        max_uses: int = 1,
        expires_at=None,
    ) -> GiftCard:
        code = code.strip().upper()
        existing = await session.execute(
            select(GiftCard).where(GiftCard.code == code)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Código já existe")

        gift = GiftCard(
            code=code,
            value=value,
            max_uses=max_uses,
            uses_count=0,
            status=GiftCardStatus.ACTIVE,
            expires_at=expires_at,
            created_by=admin_id,
        )
        session.add(gift)
        await session.flush()
        return gift

    @staticmethod
    async def redeem(
        session: AsyncSession, user_id: int, code: str
    ) -> Decimal:
        code = code.strip().upper()
        result = await session.execute(
            select(GiftCard).where(GiftCard.code == code).with_for_update()
        )
        gift = result.scalar_one_or_none()
        if not gift:
            raise ValueError("Gift não encontrado.")
        if gift.status != GiftCardStatus.ACTIVE:
            raise ValueError("Gift inativo ou esgotado.")
        if gift.expires_at and gift.expires_at < datetime.now(timezone.utc):
            gift.status = GiftCardStatus.EXPIRED
            raise ValueError("Gift expirado.")
        if gift.uses_count >= gift.max_uses:
            gift.status = GiftCardStatus.USED
            raise ValueError("Gift já utilizado.")

        gift.uses_count += 1
        if gift.uses_count >= gift.max_uses:
            gift.status = GiftCardStatus.USED

        await BalanceService.add_balance(
            session,
            user_id,
            gift.value,
            TransactionType.GIFT_CARD,
            description=f"Gift {gift.code}",
        )
        session.add(
            GiftCardRedemption(
                gift_card_id=gift.id,
                user_id=user_id,
                amount=gift.value,
            )
        )
        await session.flush()
        return gift.value
