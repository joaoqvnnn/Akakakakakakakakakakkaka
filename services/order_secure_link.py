import hashlib
import hmac
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Order, User


def _secret() -> str:
    return getattr(settings, "WITHDRAW_WEB_SECRET", None) or settings.BOT_TOKEN


def make_order_token(order_uuid: str) -> str:
    return hmac.new(
        _secret().encode(),
        order_uuid.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]


def verify_order_token(order_uuid: str, token: str) -> bool:
    expected = make_order_token(order_uuid)
    return hmac.compare_digest(expected, token or "")


class OrderSecureService:
    @staticmethod
    def public_url(order_uuid: str) -> str:
        base = getattr(settings, "WITHDRAW_WEB_BASE_URL", "http://127.0.0.1:8080")
        token = make_order_token(order_uuid)
        return f"{base.rstrip('/')}/pedido/{order_uuid}?t={token}"

    @staticmethod
    async def get_order(
        session: AsyncSession, order_uuid: str, token: str
    ) -> Optional[Order]:
        if not verify_order_token(order_uuid, token):
            return None
        result = await session.execute(select(Order).where(Order.uuid == order_uuid))
        return result.scalar_one_or_none()

    @staticmethod
    def check_user_password(user: User, password: str, fallback: str) -> bool:
        if user.withdraw_password_hash:
            h = hashlib.sha256(password.encode("utf-8")).hexdigest()
            return h == user.withdraw_password_hash
        return password == (fallback or "")
