from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, AffiliateWithdraw
from keyboards.client_dynamic import affiliates_kb, main_menu_kb
from services.settings_service import SettingsService

router = Router(name="affiliates")


@router.callback_query(F.data == "affiliates")
async def cb_affiliates(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    enabled = await SettingsService.get_bool(session, "affiliate_enabled")
    commission = await SettingsService.get(session, "affiliate_commission_percent")
    min_w = await SettingsService.get_float(session, "affiliate_min_withdraw")

    bot_user = (getattr(settings, "BOT_USERNAME", None) or "larizinhastorebot").lstrip("@")
    link = f"https://t.me/{bot_user}?start={db_user.id}"

    avg = 0.0
    if db_user.total_referrals:
        avg = float(db_user.affiliate_earned_total or 0) / max(db_user.total_referrals, 1)

    remaining = max(0, 5 - (db_user.total_referrals or 0))
    status = "Ativo" if enabled else "Desativado"

    text = (
        f"💰 <b>PROGRAMA DE AFILIADOS</b>\n\n"
        f"⚙️ Status: <b>{status}</b>\n"
        f"🧲 Sua comissão: <b>{commission}%</b> (de todas recargas do indicado)\n\n"
        f"👥 Indicações: <b>{db_user.total_referrals}</b>\n"
        f"🪙 Total ganho: <b>R$ {float(db_user.affiliate_earned_total or 0):.2f}</b>\n"
        f"📊 Média: <b>R$ {avg:.2f}</b>\n"
        f"💰 Saque mínimo: <b>R$ {min_w:.2f}</b>\n\n"
        f"🔥 Saldo de comissões: <b>R$ {db_user.affiliate_balance:.2f}</b>\n"
        f"⭐ Pontos: <b>{db_user.affiliate_points}</b>\n\n"
        f"🌱 Nível: <b>Iniciante</b>\n"
        f"🎯 Próxima meta: 5 ({remaining} restantes)\n\n"
        f"ℹ️ Seus indicados geram comissão nas recargas.\n"
        f"🔗 Seu link:\n<code>{link}</code>"
    )
    can = float(db_user.affiliate_balance or 0) >= float(min_w) and enabled
    kb = await affiliates_kb(session, can)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "affiliate_copy_link")
async def cb_copy_link(callback: CallbackQuery, db_user: User):
    bot_user = (getattr(settings, "BOT_USERNAME", None) or "larizinhastorebot").lstrip("@")
    link = f"https://t.me/{bot_user}?start={db_user.id}"
    await callback.answer("Link na mensagem abaixo")
    await callback.message.answer(f"🔗 Seu link de afiliado:\n{link}")


@router.callback_query(F.data == "affiliate_history")
async def cb_aff_history(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from services.buttons import ButtonService

    min_w = await SettingsService.get_float(session, "affiliate_min_withdraw")
    result = await session.execute(
        select(AffiliateWithdraw)
        .where(AffiliateWithdraw.user_id == db_user.id)
        .order_by(AffiliateWithdraw.created_at.desc())
        .limit(15)
    )
    items = list(result.scalars().all())

    if not items:
        text = (
            f"📊 <b>HISTÓRICO DE SAQUES</b>\n\n"
            f"Você ainda não solicitou nenhum saque.\n\n"
            f"📉 Saque mínimo atual: <b>R$ {min_w:.2f}</b>"
        )
    else:
        lines = ["📊 <b>HISTÓRICO DE SAQUES</b>\n"]
        for w in items:
            dt = w.created_at.strftime("%d/%m/%Y %H:%M") if w.created_at else "—"
            lines.append(
                f"• R$ {w.amount:.2f} | {w.status.value} | {w.payment_method} | {dt}"
            )
        text = "\n".join(lines)

    back = await ButtonService.get(session, "btn_back")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=back, callback_data="affiliates"))
    await callback.message.edit_text(
        text, reply_markup=b.as_markup(), parse_mode="HTML"
    )
    await callback.answer()
