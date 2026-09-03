import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Order, OrderStatus

logger = logging.getLogger(__name__)


class AIAssistant:
    """
    Interpreta frases como:
      - quero ver meu histórico
      - minhas compras
      - meu saldo
    Usa OpenAI se OPENAI_API_KEY existir; senão regras locais.
    """

    @staticmethod
    def _local_intent(text: str) -> str:
        t = (text or "").lower()
        if any(w in t for w in ("histórico", "historico", "compras", "pedidos")):
            return "history"
        if "saldo" in t or "carteira" in t:
            return "balance"
        if "afiliad" in t or "indicação" in t or "indicacao" in t:
            return "affiliate"
        if "suporte" in t or "ajuda" in t:
            return "support"
        return "unknown"

    @staticmethod
    async def classify(text: str) -> str:
        key = getattr(settings, "OPENAI_API_KEY", None) or ""
        if not key:
            return AIAssistant._local_intent(text)
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=key)
            resp = await client.chat.completions.create(
                model=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classifique a intenção do usuário da loja Telegram. "
                            "Responda só uma palavra: history|balance|affiliate|support|unknown"
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0,
            )
            label = (resp.choices[0].message.content or "unknown").strip().lower()
            if label in ("history", "balance", "affiliate", "support", "unknown"):
                return label
        except Exception:
            logger.exception("OpenAI classify failed")
        return AIAssistant._local_intent(text)

    @staticmethod
    async def build_history_text(session: AsyncSession, user: User) -> str:
        result = await session.execute(
            select(Order)
            .where(
                Order.user_id == user.id,
                Order.status == OrderStatus.DELIVERED,
            )
            .order_by(Order.created_at.desc())
            .limit(20)
        )
        orders = list(result.scalars().all())
        if not orders:
            return "Você ainda não possui compras."
        lines = [f"🧾 Histórico de {user.id} ({len(orders)} pedidos)\n"]
        for o in orders:
            lines.append(
                f"• {o.created_at.strftime('%d/%m/%Y')} | R$ {o.total_price:.2f} | "
                f"{o.uuid[:8]}… | {o.delivery_content or '—'}"
            )
        return "\n".join(lines)
