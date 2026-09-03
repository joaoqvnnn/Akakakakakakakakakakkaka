import asyncio
import logging

from database.session import AsyncSessionLocal
from services.payment import PaymentService

logger = logging.getLogger(__name__)
_running = False


async def expire_pix_loop(interval_seconds: int = 60) -> None:
    global _running
    _running = True
    payment_service = PaymentService()
    logger.info("Scheduler PIX expire iniciado")
    while _running:
        try:
            async with AsyncSessionLocal() as session:
                n = await payment_service.expire_pending(session)
                await session.commit()
                if n:
                    logger.info("PIX expirados: %s", n)
        except Exception:
            logger.exception("Erro expire_pix_loop")
        await asyncio.sleep(interval_seconds)


def stop_scheduler() -> None:
    global _running
    _running = False
