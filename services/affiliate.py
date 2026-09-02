from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, TransactionType, AffiliateWithdraw, WithdrawStatus
from services.balance import BalanceService
from services.settings_service import SettingsService


class AffiliateService:
    """Comissão por indicação e solicitação de saque."""

    @staticmethod
    async def pay_commission(
        session: AsyncSession,
        referred_user_id: int,
        order_amount: Decimal,
        order_id: int,
    ) -> Optional[Decimal]:
        enabled = await SettingsService.get_bool(session, "affiliate_enabled")
        if not enabled:
            return None

        user = await session.get(User, referred_user_id)
        if not user or not user.referred_by:
            return None

        percent = Decimal(
            str(
                await SettingsService.get(
                    session, "affiliate_commission_percent", "20"
                )
            )
        )
        if percent <= 0:
            return None

        commission = (order_amount * percent / Decimal("100")).quantize(
            Decimal("0.01")
        )
        if commission <= 0:
            return None

        await BalanceService.add_balance(
            session=session,
            user_id=user.referred_by,
            amount=commission,
            tx_type=TransactionType.AFFILIATE_COMMISSION,
            description=f"Comissão compra #{order_id}",
            order_id=order_id,
        )
        return commission

    @staticmethod
    async def add_points_on_recharge(
        session: AsyncSession,
        referred_user_id: int,
    ) -> Optional[int]:
        """Pontos para o indicador quando o indicado recarrega (sistema de pontos)."""
        enabled = await SettingsService.get_bool(session, "affiliate_enabled")
        if not enabled:
            return None

        user = await session.get(User, referred_user_id)
        if not user or not user.referred_by:
            return None

        points = await SettingsService.get_int(session, "points_per_recharge")
        if points <= 0:
            return None

        referrer = await session.get(User, user.referred_by, with_for_update=True)
        if not referrer:
            return None

        referrer.affiliate_points += points
        await session.flush()
        return points

    @staticmethod
    async def convert_points_to_balance(
        session: AsyncSession,
        user_id: int,
    ) -> Decimal:
        """Converte pontos em saldo (mínimo + multiplicador do admin)."""
        user = await session.get(User, user_id, with_for_update=True)
        if not user:
            raise ValueError("Usuário não encontrado")

        min_points = await SettingsService.get_int(session, "points_min_convert")
        mult = Decimal(
            str(await SettingsService.get(session, "points_multiplier", "0.01"))
        )

        if user.affiliate_points < min_points:
            raise ValueError(
                f"Mínimo de {min_points} pontos para converter. Você tem {user.affiliate_points}."
            )

        points = user.affiliate_points
        amount = (Decimal(points) * mult).quantize(Decimal("0.01"))
        if amount <= 0:
            raise ValueError("Valor convertido inválido")

        user.affiliate_points = 0

        await BalanceService.add_balance(
            session=session,
            user_id=user_id,
            amount=amount,
            tx_type=TransactionType.POINTS_CONVERT,
            description=f"Conversão de {points} pontos",
        )
        return amount

    @staticmethod
    async def request_withdraw(
        session: AsyncSession,
        user_id: int,
        amount: Decimal,
    ) -> AffiliateWithdraw:
        """
        Reserva o valor de comissão e cria saque PENDING.
        Dados bancários / Pix entram depois (Telegram ou página web).
        """
        min_withdraw = Decimal(
            str(
                await SettingsService.get(
                    session, "affiliate_min_withdraw", "20"
                )
            )
        )
        if amount < min_withdraw:
            raise ValueError(f"Saque mínimo: R$ {min_withdraw:.2f}")

        user = await session.get(User, user_id, with_for_update=True)
        if not user:
            raise ValueError("Usuário não encontrado")
        if user.affiliate_balance < amount:
            raise ValueError("Saldo de comissão insuficiente")

        user.affiliate_balance -= amount

        withdraw = AffiliateWithdraw(
            user_id=user_id,
            amount=amount,
            status=WithdrawStatus.PENDING,
            payment_method="pix",
        )
        session.add(withdraw)
        await session.flush()
        return withdraw
