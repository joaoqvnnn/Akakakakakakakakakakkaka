from __future__ import annotations

from typing import Dict, Optional
from dataclasses import dataclass
import time


@dataclass
class WaPending:
    order_id: int
    user_id: int
    phone: str
    created_at: float


class WhatsAppOrderFlow:
    _pending: Dict[str, WaPending] = {}
    TTL = 15 * 60

    @classmethod
    def set_pending(cls, phone: str, order_id: int, user_id: int) -> None:
        digits = "".join(c for c in phone if c.isdigit())
        cls._pending[digits] = WaPending(
            order_id=order_id, user_id=user_id, phone=digits, created_at=time.time()
        )

    @classmethod
    def pop_pending(cls, phone: str) -> Optional[WaPending]:
        digits = "".join(c for c in phone if c.isdigit())
        for key in (digits, digits[2:] if digits.startswith("55") else "55" + digits):
            item = cls._pending.get(key)
            if item:
                if time.time() - item.created_at > cls.TTL:
                    cls._pending.pop(key, None)
                    return None
                cls._pending.pop(key, None)
                return item
        return None

    @classmethod
    def get_pending(cls, phone: str) -> Optional[WaPending]:
        digits = "".join(c for c in phone if c.isdigit())
        for key in list(cls._pending.keys()):
            if key == digits or key.endswith(digits) or digits.endswith(key):
                item = cls._pending[key]
                if time.time() - item.created_at > cls.TTL:
                    cls._pending.pop(key, None)
                    return None
                return item
        return None
