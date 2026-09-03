from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import StockItem, Product


class StockService:
    @staticmethod
    async def reserve_items(
        session: AsyncSession, product_id: int, quantity: int
    ) -> List[StockItem]:
        result = await session.execute(
            select(StockItem)
            .where(
                StockItem.product_id == product_id,
                StockItem.is_sold.is_(False),
            )
            .order_by(StockItem.id)
            .limit(quantity)
            .with_for_update()
        )
        items = list(result.scalars().all())
        return items

    @staticmethod
    async def add_stock(
        session: AsyncSession, product_id: int, contents: List[str]
    ) -> int:
        product = await session.get(Product, product_id)
        if not product:
            raise ValueError("Produto não encontrado")
        count = 0
        for content in contents:
            content = (content or "").strip()
            if not content:
                continue
            session.add(StockItem(product_id=product_id, content=content))
            count += 1
        product.stock_count = (product.stock_count or 0) + count
        await session.flush()
        return count

    @staticmethod
    async def release_items(session: AsyncSession, items: List[StockItem]) -> None:
        for item in items:
            if item.is_sold:
                continue
            # itens não vendidos permanecem disponíveis
        await session.flush()
