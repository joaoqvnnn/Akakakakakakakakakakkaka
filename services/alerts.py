from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Product, StockAlert


class AlertService:
    @staticmethod
    async def toggle_alert(
        session: AsyncSession, user_id: int, product_id: int
    ) -> bool:
        """Ativa/desativa alerta. Retorna True se ficou ativo."""
        result = await session.execute(
            select(StockAlert).where(
                StockAlert.user_id == user_id,
                StockAlert.product_id == product_id,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.is_active = not row.is_active
            await session.flush()
            return row.is_active

        row = StockAlert(user_id=user_id, product_id=product_id, is_active=True)
        session.add(row)
        await session.flush()
        return True

    @staticmethod
    async def list_active_map(session: AsyncSession, user_id: int) -> dict:
        result = await session.execute(
            select(StockAlert).where(
                StockAlert.user_id == user_id,
                StockAlert.is_active.is_(True),
            )
        )
        return {a.product_id: True for a in result.scalars().all()}

    @staticmethod
    async def notify_restock(
        session: AsyncSession,
        bot: Bot,
        product_id: int,
        added: int = 1,
    ) -> int:
        product = await session.get(Product, product_id)
        if not product:
            return 0

        result = await session.execute(
            select(StockAlert).where(
                StockAlert.product_id == product_id,
                StockAlert.is_active.is_(True),
            )
        )
        alerts = list(result.scalars().all())
        if not alerts:
            return 0

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="💳 Comprar agora",
                callback_data=f"product:{product_id}",
            )
        )
        builder.row(
            InlineKeyboardButton(text="🏠 Menu", callback_data="main_menu")
        )
        kb = builder.as_markup()

        text = (
            f"📢 <b>Estoque abastecido!</b>\n\n"
            f"{product.emoji} <b>{product.name}</b>\n"
            f"📦 Entraram <b>{added}</b> unidade(s)\n"
            f"📦 Estoque atual: <b>{product.stock_count}</b>\n"
            f"💵 Preço: <b>R$ {product.price:.2f}</b>\n\n"
            f"Corra antes que acabe!"
        )

        sent = 0
        for alert in alerts:
            try:
                await bot.send_message(
                    alert.user_id,
                    text,
                    reply_markup=kb,
                    parse_mode="HTML",
                )
                sent += 1
            except Exception:
                continue
        return sent
