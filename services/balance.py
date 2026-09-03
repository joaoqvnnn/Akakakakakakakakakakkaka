from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Transaction, TransactionType


class BalanceService:
    @staticmethod
    async def add_balance(
        session: AsyncSession,
        user_id: int,
        amount: Decimal,
        tx_type: TransactionType,
        description: str = "",
        admin_id: Optional[int] = None,
        payment_id: Optional[int] = None,
    ) -> User:
        result = await session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Usuário não encontrado")

        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Valor inválido")

        user.balance = (user.balance or Decimal("0")) + amount
        if tx_type == TransactionType.DEPOSIT:
            user.total_deposited = (user.total_deposited or Decimal("0")) + amount

        session.add(
            Transaction(
                user_id=user_id,
                type=tx_type,
                amount=amount,
                balance_after=user.balance,
                description=description,
                admin_id=admin_id,
                payment_id=payment_id,
            )
        )
        await session.flush()
        return user

    @staticmethod
    async def remove_balance(
        session: AsyncSession,
        user_id: int,
        amount: Decimal,
        tx_type: TransactionType,
        description: str = "",
        admin_id: Optional[int] = None,
    ) -> User:
        result = await session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Usuário não encontrado")

        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Valor inválido")
        if (user.balance or Decimal("0")) < amount:
            raise ValueError("Saldo insuficiente")

        user.balance -= amount
        session.add(
            Transaction(
                user_id=user_id,
                type=tx_type,
                amount=-amount,
                balance_after=user.balance,
                description=description,
                admin_id=admin_id,
            )
        )
        await session.flush()
        return user
