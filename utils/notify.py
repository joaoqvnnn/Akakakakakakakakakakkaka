from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Payment
from database.session import AsyncSessionLocal
from services.messages import MessageService


async def notify_user_payment_approved(bot: Bot, payment: Payment) -> None:
    amount = payment.amount
    bonus = payment.bonus_amount or 0
    total = amount + (bonus or 0)
    text = (
        f"✅ <b>PAGAMENTO APROVADO!</b>\n\n"
        f"💰 Valor: <b>R$ {amount:.2f}</b>\n"
        f"🎁 Bônus: <b>R$ {float(bonus):.2f}</b>\n"
        f"💳 Total creditado: <b>R$ {float(total):.2f}</b>"
    )
    try:
        async with AsyncSessionLocal() as session:
            tpl = await MessageService.get_rendered(
                session,
                "payment_approved",
                amount=f"{amount:.2f}",
                bonus=f"{float(bonus):.2f}",
                total=f"{float(total):.2f}",
            )
            text = tpl["content"]
            await session.commit()
    except Exception:
        pass
    try:
        await bot.send_message(payment.user_id, text, parse_mode="HTML")
    except Exception:
        pass
