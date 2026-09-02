from typing import List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Product, StockItem, ProductStatus


class StockService:
    """Estoque unidade a unidade, com proteção contra venda duplicada."""

    @staticmethod
    async def get_available_count(session: AsyncSession, product_id: int) -> int:
        result = await session.execute(
            select(func.count(StockItem.id)).where(
                StockItem.product_id == product_id,
                StockItem.is_sold.is_(False),
            )
        )
        return result.scalar_one() or 0

    @staticmethod
    async def reserve_items(
        session: AsyncSession,
        product_id: int,
        quantity: int,
        order_id: int,
    ) -> List[StockItem]:
        result = await session.execute(
            select(StockItem)
            .where(
                StockItem.product_id == product_id,
                StockItem.is_sold.is_(False),
            )
            .order_by(StockItem.id)
            .limit(quantity)
            .with_for_update(skip_locked=True)
        )
        items = list(result.scalars().all())

        if len(items) < quantity:
            raise ValueError(f"Estoque insuficiente. Disponível: {len(items)}")

        for item in items:
            item.is_sold = True
            item.order_id = order_id

        product = await session.get(Product, product_id, with_for_update=True)
        if product:
            product.stock_count = max(0, product.stock_count - quantity)
            product.sold_count += quantity
            if product.stock_count == 0:
                product.status = ProductStatus.OUT_OF_STOCK

        await session.flush()
        return items

    @staticmethod
    async def add_stock(
        session: AsyncSession,
        product_id: int,
        contents: List[str],
    ) -> int:
        product = await session.get(Product, product_id, with_for_update=True)
        if not product:
            raise ValueError("Produto não encontrado")

        items = [
            StockItem(product_id=product_id, content=c.strip())
            for c in contents
            if c and c.strip()
        ]
        if not items:
            return 0

        session.add_all(items)
        product.stock_count += len(items)
        if product.status == ProductStatus.OUT_OF_STOCK and len(items) > 0:
            product.status = ProductStatus.ACTIVE

        await session.flush()
        return len(items)

    @staticmethod
    async def release_items(session: AsyncSession, order_id: int) -> None:
        result = await session.execute(
            select(StockItem).where(StockItem.order_id == order_id)
        )
        items = list(result.scalars().all())
        if not items:
            return

        product_id = items[0].product_id
        for item in items:
            item.is_sold = False
            item.order_id = None
            item.sold_at = None

        product = await session.get(Product, product_id, with_for_update=True)
        if product:
            product.stock_count += len(items)
            product.sold_count = max(0, product.sold_count - len(items))
            if product.status == ProductStatus.OUT_OF_STOCK:
                product.status = ProductStatus.ACTIVE

        await session.flush()
