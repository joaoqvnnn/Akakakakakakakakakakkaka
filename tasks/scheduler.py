import asyncio
import logging

from database.session import AsyncSessionLocal
from services.payment import PaymentService

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []
_running = False


async def expire_pix_loop(interval_seconds: int = 60):
    payment_service = PaymentService()
    while _running:
        try:
            async with AsyncSessionLocal() as session:
                count = await payment_service.expire_pending(session)
                await session.commit()
                if count:
                    logger.info("PIX expirados: %s", count)
        except Exception:
            logger.exception("Erro ao expirar PIX")
        await asyncio.sleep(interval_seconds)


async def start_background_tasks():
    global _running, _tasks
    if _running:
        return
    _running = True
    _tasks = [asyncio.create_task(expire_pix_loop(60))]
    logger.info("Tasks em background iniciadas")


async def stop_background_tasks():
    global _running, _tasks
    _running = False
    for t in _tasks:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    _tasks = []
    logger.info("Tasks finalizadas")
