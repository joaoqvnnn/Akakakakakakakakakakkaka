from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Payment, PaymentStatus
from handlers.admin.panel import is_admin
from keyboards.admin import admin_payments_kb, admin_back_kb

router = Router(name="admin_payments")

STATUS_MAP = {
    "approved": PaymentStatus.APPROVED,
    "pending": PaymentStatus.PENDING,
    "expired": PaymentStatus.EXPIRED,
    "cancelled": PaymentStatus.CANCELLED,
}


@router.callback_query(F.data.startswith("admin:payments:"))
async def cb_payments_list(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    key = callback.data.split(":")[2]
    status = STATUS_MAP.get(key)
    if not status:
        await callback.answer("Filtro inválido.")
        return

    result = await session.execute(
        select(Payment)
        .where(Payment.status == status)
        .order_by(Payment.created_at.desc())
        .limit(15)
    )
    payments = list(result.scalars().all())

    if not payments:
        text = f"Nenhum pagamento <b>{key}</b>."
    else:
        lines = [f"💳 <b>Pagamentos — {key}</b>\n"]
        for p in payments:
            lines.append(
                f"#{p.id} | user <code>{p.user_id}</code> | "
                f"R$ {p.amount:.2f} | {p.created_at.strftime('%d/%m %H:%M')}"
            )
        text = "\n".join(lines)

    await callback.message.edit_text(
        text, reply_markup=admin_payments_kb(), parse_mode="HTML"
    )
    await callback.answer()
