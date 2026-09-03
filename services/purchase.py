from decimal import Decimal
from datetime import datetime, timedelta, timezone
import uuid as uuid_lib
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    User,
    Product,
    ProductStatus,
    Order,
    OrderStatus,
    PaymentMethod,
    TransactionType,
)
from services.balance import BalanceService
from services.stock import StockService


class PurchaseService:
    @staticmethod
    async def check_can_buy(
        session: AsyncSession,
        user_id: int,
        product_id: int,
        quantity: int = 1,
    ) -> Tuple[bool, str]:
        if quantity < 1:
            return False, "Quantidade inválida"
        product = await session.get(Product, product_id)
        if not product or product.status != ProductStatus.ACTIVE:
            return False, "Produto indisponível"
        if (product.stock_count or 0) < quantity:
            return False, "Estoque insuficiente"
        user = await session.get(User, user_id)
        if not user:
            return False, "Usuário não encontrado"
        total = product.price * quantity
        if user.balance < total:
            return False, "Saldo insuficiente"
        return True, "ok"

    @staticmethod
    async def buy_with_balance(
        session: AsyncSession,
        user_id: int,
        product_id: int,
        quantity: int = 1,
    ) -> Order:
        can, reason = await PurchaseService.check_can_buy(
            session, user_id, product_id, quantity
        )
        if not can:
            raise ValueError(reason)

        product = await session.get(Product, product_id)
        user = await session.get(User, user_id)
        total = product.price * quantity

        items = await StockService.reserve_items(session, product_id, quantity)
        if len(items) < quantity:
            raise ValueError("Estoque insuficiente no momento da reserva")

        delivery_parts = [it.content for it in items if it.content]
        delivery_content = "\n".join(delivery_parts)

        await BalanceService.remove_balance(
            session,
            user_id,
            total,
            TransactionType.PURCHASE,
            description=f"Compra {product.name} x{quantity}",
        )

        expires_at = None
        days = product.validity_days or product.warranty_days or 0
        if days > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(days=days)

        order = Order(
            uuid=str(uuid_lib.uuid4()),
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=product.price,
            total_price=total,
            status=OrderStatus.DELIVERED,
            payment_method=PaymentMethod.BALANCE,
            delivery_content=delivery_content,
            expires_at=expires_at,
            delivered_at=datetime.now(timezone.utc),
        )
        session.add(order)

        for it in items:
            it.is_sold = True
            it.sold_at = datetime.now(timezone.utc)
            it.order_id = None  # preenchido após flush se modelo tiver FK

        product.stock_count = max(0, (product.stock_count or 0) - quantity)
        product.sold_count = (product.sold_count or 0) + quantity
        if product.stock_count == 0:
            product.status = ProductStatus.OUT_OF_STOCK

        user.total_spent = (user.total_spent or Decimal("0")) + total
        await session.flush()

        for it in items:
            if hasattr(it, "order_id"):
                it.order_id = order.id
        await session.flush()
        return order
