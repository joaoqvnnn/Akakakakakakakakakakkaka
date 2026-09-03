from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from services.alerts import AlertService


async def notify_if_restocked(
    session: AsyncSession,
    bot: Bot,
    product_id: int,
    added: int,
) -> int:
    """Avisa quem ativou alerta quando o estoque aumenta."""
    if added <= 0:
        return 0
    return await AlertService.notify_restock(session, bot, product_id, added)
