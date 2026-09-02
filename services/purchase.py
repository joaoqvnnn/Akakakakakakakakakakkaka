from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Order,
    OrderStatus,
    PaymentMethod,
    Product,
    ProductStatus,
    TransactionType,
    User,
)
from services.balance import BalanceService
from services.stock import StockService


class PurchaseService:
    """Compra com saldo: trava estoque + debita + entrega (sem venda duplicada)."""

    @staticmethod
    async def check_can_buy(
        session: AsyncSession,
        user_id: int,
        product_id: int,
        quantity: int = 1,
    ) -> Tuple[bool, str, Decimal]:
        """
        Retorna: (pode_comprar, mensagem, valor_faltante)
        """
        if quantity < 1:
            return False, "Quantidade inválida", Decimal("0")

        product = await session.get(Product, product_id)
        if not product or product.status != ProductStatus.ACTIVE:
            return False, "Produto indisponível", Decimal("0")

        available = await StockService.get_available_count(session, product_id)
        if available < quantity:
            return False, f"Estoque insuficiente. Disponível: {available}", Decimal("0")

        user = await session.get(User, user_id)
        if not user:
            return False, "Usuário não encontrado", Decimal("0")

        total = product.price * quantity
        if user.balance >= total:
            return True, "OK", Decimal("0")

        missing = total - user.balance
        return False, "Saldo insuficiente", missing

    @staticmethod
    async def buy_with_balance(
        session: AsyncSession,
        user_id: int,
        product_id: int,
        quantity: int = 1,
    ) -> Tuple[Order, List[str]]:
        """
        Executa a compra.
        Retorna (pedido, lista de conteúdos entregues).
        """
        if quantity < 1:
            raise ValueError("Quantidade inválida")

        product = await session.get(Product, product_id, with_for_update=True)
        if not product or product.status != ProductStatus.ACTIVE:
            raise ValueError("Produto indisponível")

        user = await session.get(User, user_id, with_for_update=True)
        if not user:
            raise ValueError("Usuário não encontrado")

        total_price = product.price * quantity
        if user.balance < total_price:
            raise ValueError("Saldo insuficiente")

        order = Order(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=product.price,
            total_price=total_price,
            status=OrderStatus.PENDING,
            payment_method=PaymentMethod.BALANCE,
        )
        session.add(order)
        await session.flush()

        items = await StockService.reserve_items(
            session, product_id, quantity, order.id
        )

        await BalanceService.remove_balance(
            session=session,
            user_id=user_id,
            amount=total_price,
            tx_type=TransactionType.PURCHASE,
            description=f"Compra: {product.name} x{quantity}",
            order_id=order.id,
        )

        delivery_contents = [item.content for item in items]
        order.delivery_content = "\n".join(delivery_contents)
        order.status = OrderStatus.DELIVERED
        order.delivered_at = datetime.now(timezone.utc)

        if product.validity_days:
            order.expires_at = datetime.now(timezone.utc) + timedelta(
                days=product.validity_days * quantity
                if quantity == 1
                else product.validity_days
            )
        elif product.warranty_days:
            order.expires_at = datetime.now(timezone.utc) + timedelta(
                days=product.warranty_days
            )

        # Comissão de afiliado (se houver indicador)
        if user.referred_by:
            from services.affiliate import AffiliateService

            await AffiliateService.pay_commission(
                session=session,
                referred_user_id=user_id,
                order_amount=total_price,
                order_id=order.id,
            )

        await session.flush()
        return order, delivery_contents
