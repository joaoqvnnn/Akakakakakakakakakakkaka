import logging

from aiogram import Bot

from database.models import Payment

logger = logging.getLogger(__name__)


async def notify_user_payment_approved(bot: Bot, payment: Payment) -> None:
    try:
        text = (
            f"✅ <b>PAGAMENTO APROVADO!</b>\n\n"
            f"💰 Valor: <b>R$ {payment.amount:.2f}</b>\n"
            f"🎁 Bônus: <b>R$ {payment.bonus_amount:.2f}</b>\n"
            f"💳 Total creditado: <b>R$ {payment.total_credited:.2f}</b>\n\n"
            f"Seu saldo já está disponível. Use /saldo para conferir."
        )
        await bot.send_message(
            chat_id=payment.user_id,
            text=text,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Falha ao notificar user %s: %s", payment.user_id, e)
