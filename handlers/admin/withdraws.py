from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from database.models import User, AffiliateWithdraw, WithdrawStatus
from handlers.admin.panel import is_admin

router = Router(name="admin_withdraws")


@router.callback_query(F.data == "admin:withdraws")
async def cb_withdraws_list(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    result = await session.execute(
        select(AffiliateWithdraw)
        .where(AffiliateWithdraw.status == WithdrawStatus.PENDING)
        .order_by(AffiliateWithdraw.created_at.desc())
        .limit(20)
    )
    items = list(result.scalars().all())

    if not items:
        text = "✅ Nenhum saque pendente."
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:transactions"))
        await callback.message.edit_text(text, reply_markup=b.as_markup())
        await callback.answer()
        return

    lines = ["💸 <b>SAQUES PENDENTES</b>\n"]
    builder = InlineKeyboardBuilder()
    for w in items:
        lines.append(
            f"#{w.id} user <code>{w.user_id}</code> "
            f"R$ {w.amount:.2f} | {w.payment_method}"
        )
        builder.row(
            InlineKeyboardButton(
                text=f"#{w.id} R$ {w.amount:.2f}",
                callback_data=f"admin:wd_view:{w.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:transactions"))
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:wd_view:"))
async def cb_wd_view(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    wid = int(callback.data.split(":")[2])
    w = await session.get(AffiliateWithdraw, wid)
    if not w:
        await callback.answer("Não encontrado.", show_alert=True)
        return

    text = (
        f"💸 <b>Saque #{w.id}</b>\n\n"
        f"User: <code>{w.user_id}</code>\n"
        f"Valor: <b>R$ {w.amount:.2f}</b>\n"
        f"Método: {w.payment_method}\n"
        f"Status: {w.status.value}\n"
        f"Pix: <code>{w.pix_key or '—'}</code> ({w.pix_key_type or '—'})\n"
        f"Banco: {w.bank_name or '—'}\n"
        f"Agência: {w.agency or '—'}\n"
        f"Conta: {w.account or '—'}\n"
        f"Titular: {w.holder_name or '—'}\n"
        f"UUID: <code>{w.uuid}</code>"
    )
    b = InlineKeyboardBuilder()
    if w.status == WithdrawStatus.PENDING:
        b.row(
            InlineKeyboardButton(
                text="✅ Marcar pago", callback_data=f"admin:wd_pay:{w.id}"
            ),
            InlineKeyboardButton(
                text="❌ Rejeitar", callback_data=f"admin:wd_reject:{w.id}"
            ),
        )
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:withdraws"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:wd_pay:"))
async def cb_wd_pay(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    wid = int(callback.data.split(":")[2])
    w = await session.get(AffiliateWithdraw, wid)
    if not w or w.status != WithdrawStatus.PENDING:
        await callback.answer("Inválido.", show_alert=True)
        return
    w.status = WithdrawStatus.PAID
    w.processed_by_admin_id = db_user.id
    w.processed_at = datetime.now(timezone.utc)
    try:
        await callback.bot.send_message(
            w.user_id,
            f"✅ Seu saque de <b>R$ {w.amount:.2f}</b> foi pago!",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer("Marcado como pago.")
    callback.data = f"admin:wd_view:{wid}"
    await cb_wd_view(callback, session, db_user)


@router.callback_query(F.data.startswith("admin:wd_reject:"))
async def cb_wd_reject(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    wid = int(callback.data.split(":")[2])
    w = await session.get(AffiliateWithdraw, wid)
    if not w or w.status != WithdrawStatus.PENDING:
        await callback.answer("Inválido.", show_alert=True)
        return

    # Devolve saldo de comissão
    user = await session.get(User, w.user_id)
    if user:
        user.affiliate_balance += w.amount

    w.status = WithdrawStatus.REJECTED
    w.processed_by_admin_id = db_user.id
    w.processed_at = datetime.now(timezone.utc)
    w.rejection_reason = "Rejeitado pelo admin"

    try:
        await callback.bot.send_message(
            w.user_id,
            f"❌ Saque de R$ {w.amount:.2f} rejeitado. Valor devolvido ao saldo de comissão.",
        )
    except Exception:
        pass
    await callback.answer("Rejeitado e estornado.")
    await cb_withdraws_list(callback, session, db_user)
