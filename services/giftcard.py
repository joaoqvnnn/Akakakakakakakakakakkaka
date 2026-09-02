from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import GiftCard, GiftCardStatus, TransactionType
from services.balance import BalanceService


class GiftCardService:
    """Resgate de gift card / cupom com validação real."""

    @staticmethod
    async def redeem(
        session: AsyncSession,
        user_id: int,
        code: str,
    ) -> Decimal:
        code = (code or "").strip().upper()
        if not code:
            raise ValueError("Código inválido")

        result = await session.execute(
            select(GiftCard).where(GiftCard.code == code).with_for_update()
        )
        gift = result.scalar_one_or_none()

        if not gift:
            raise ValueError("Gift Card não encontrado ou inválido")

        if gift.status != GiftCardStatus.ACTIVE:
            raise ValueError("Gift Card inválido ou já utilizado")

        if gift.expires_at and gift.expires_at < datetime.now(timezone.utc):
            gift.status = GiftCardStatus.EXPIRED
            raise ValueError("Gift Card expirado")

        if gift.current_uses >= gift.max_uses:
            gift.status = GiftCardStatus.USED
            raise ValueError("Gift Card já esgotado")

        gift.current_uses += 1
        gift.redeemed_by = user_id
        gift.redeemed_at = datetime.now(timezone.utc)
        if gift.current_uses >= gift.max_uses:
            gift.status = GiftCardStatus.USED

        await BalanceService.add_balance(
            session=session,
            user_id=user_id,
            amount=gift.value,
            tx_type=TransactionType.GIFT_CARD,
            description=f"Gift Card {gift.code}",
            gift_card_id=gift.id,
        )
        await session.flush()
        return gift.value

    @staticmethod
    async def create(
        session: AsyncSession,
        code: str,
        value: Decimal,
        admin_id: Optional[int] = None,
        max_uses: int = 1,
        expires_at=None,
    ) -> GiftCard:
        from typing import Optional  # noqa — se precisar no topo

        code = code.strip().upper()
        gift = GiftCard(
            code=code,
            value=value,
            status=GiftCardStatus.ACTIVE,
            max_uses=max_uses,
            expires_at=expires_at,
            created_by_admin_id=admin_id,
        )
        session.add(gift)
        await session.flush()
        return gift
