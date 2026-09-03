from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, AffiliateWithdraw, WithdrawStatus
from handlers.admin.panel import is_admin
from keyboards.admin import admin_payments_kb
from services.balance import BalanceService
from database.models import TransactionType

router = Router(name="admin_withdraws")


@router.callback_query(F.data == "admin:withdraws")
async def cb_withdraws(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    result = await session.execute(
        select(AffiliateWithdraw)
        .where(AffiliateWithdraw.status == WithdrawStatus.PENDING)
        .order_by(AffiliateWithdraw.created_at.asc())
        .limit(20)
    )
    items = list(result.scalars().all())

    if not items:
        text = "💸 <b>SAQUES AFILIADOS</b>\n\nNenhum saque pendente."
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:transactions"))
        await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
        await callback.answer()
        return

    lines = ["💸 <b>SAQUES PENDENTES</b>\n"]
    b = InlineKeyboardBuilder()
    for w in items:
        lines.append(
            f"• <code>{w.uuid[:8]}</code> | user {w.user_id} | "
            f"R$ {w.amount:.2f} | {w.payment_method}"
        )
        if w.pix_key:
            lines.append(f"  PIX: <code>{w.pix_key}</code>")
        if w.bank_name:
            lines.append(f"  Banco: {w.bank_name} ag {w.agency} cc {w.account}")
        b.row(
            InlineKeyboardButton(
                text=f"✅ Pagar {w.uuid[:6]}",
                callback_data=f"admin:wd_pay:{w.id}",
            ),
            InlineKeyboardButton(
                text=f"❌ Recusar {w.uuid[:6]}",
                callback_data=f"admin:wd_rej:{w.id}",
            ),
        )
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:transactions"))
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=b.as_markup(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:wd_pay:"))
async def cb_pay(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    wid = int(callback.data.split(":")[2])
    w = await session.get(AffiliateWithdraw, wid)
    if not w or w.status != WithdrawStatus.PENDING:
        await callback.answer("Saque inválido.", show_alert=True)
        return
    w.status = WithdrawStatus.PAID
    await callback.answer("Marcado como PAGO.")
    try:
        await callback.bot.send_message(
            w.user_id,
            f"✅ Seu saque de <b>R$ {w.amount:.2f}</b> foi pago.\n"
            f"ID: <code>{w.uuid}</code>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb_withdraws(callback, session, db_user)


@router.callback_query(F.data.startswith("admin:wd_rej:"))
async def cb_rej(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    wid = int(callback.data.split(":")[2])
    w = await session.get(AffiliateWithdraw, wid)
    if not w or w.status != WithdrawStatus.PENDING:
        await callback.answer("Saque inválido.", show_alert=True)
        return

    # devolve saldo de comissão
    user = await session.get(User, w.user_id)
    if user:
        user.affiliate_balance = (user.affiliate_balance or 0) + w.amount

    w.status = WithdrawStatus.REJECTED
    await callback.answer("Recusado e saldo devolvido.")
    try:
        await callback.bot.send_message(
            w.user_id,
            f"❌ Saque de <b>R$ {w.amount:.2f}</b> recusado.\n"
            f"Saldo de comissão devolvido.\nID: <code>{w.uuid}</code>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb_withdraws(callback, session, db_user)
