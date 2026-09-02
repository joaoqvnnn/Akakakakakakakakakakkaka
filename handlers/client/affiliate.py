from decimal import Decimal

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, AffiliateWithdraw, WithdrawStatus
from keyboards.client import affiliates_kb, back_kb, main_menu_kb
from services.affiliate import AffiliateService
from services.settings_service import SettingsService

router = Router(name="affiliates")


class WithdrawStates(StatesGroup):
    waiting_amount = State()


@router.callback_query(F.data == "affiliates")
async def cb_affiliates(callback: CallbackQuery, session: AsyncSession, db_user: User):
    enabled = await SettingsService.get_bool(session, "affiliate_enabled")
    commission = await SettingsService.get(session, "affiliate_commission_percent", "20")
    min_withdraw = await SettingsService.get_float(session, "affiliate_min_withdraw")
    if min_withdraw <= 0:
        min_withdraw = float(settings.AFFILIATE_MIN_WITHDRAW)

    avg = Decimal("0.00")
    if db_user.total_referrals > 0 and db_user.total_commission_earned:
        avg = (db_user.total_commission_earned / db_user.total_referrals).quantize(
            Decimal("0.01")
        )

    link = f"https://t.me/{settings.BOT_USERNAME}?start={db_user.id}"
    can_withdraw = float(db_user.affiliate_balance) >= min_withdraw

    text = (
        f"💰 <b>PROGRAMA DE AFILIADOS</b>\n\n"
        f"⚙️ Status: <b>{'Ativo' if enabled else 'Desativado'}</b>\n"
        f"🧲 Sua comissão: <b>{commission}%</b> (de todas recargas/compras do indicado)\n\n"
        f"👥 Indicações: <b>{db_user.total_referrals}</b>\n"
        f"🪙 Total ganho: <b>R$ {db_user.total_commission_earned:.2f}</b>\n"
        f"📊 Média: <b>R$ {avg:.2f}</b>\n"
        f"💰 Saque mínimo: <b>R$ {min_withdraw:.2f}</b>\n\n"
        f"🔥 Saldo de comissões: <b>R$ {db_user.affiliate_balance:.2f}</b>\n"
        f"⭐ Pontos: <b>{db_user.affiliate_points}</b>\n\n"
        f"ℹ️ Seus indicados geram comissão conforme as regras atuais.\n\n"
        f"🔗 <b>Seu link:</b>\n"
        f"<code>{link}</code>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=affiliates_kb(can_withdraw),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "affiliate_copy_link")
async def cb_copy_link(callback: CallbackQuery, db_user: User):
    link = f"https://t.me/{settings.BOT_USERNAME}?start={db_user.id}"
    await callback.answer(link, show_alert=True)


@router.callback_query(F.data == "affiliate_withdraw")
async def cb_withdraw_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
):
    min_withdraw = await SettingsService.get_float(session, "affiliate_min_withdraw")
    if min_withdraw <= 0:
        min_withdraw = float(settings.AFFILIATE_MIN_WITHDRAW)

    if float(db_user.affiliate_balance) < min_withdraw:
        await callback.answer(
            f"Saldo insuficiente. Mínimo: R$ {min_withdraw:.2f}",
            show_alert=True,
        )
        return

    await state.set_state(WithdrawStates.waiting_amount)
    await callback.message.edit_text(
        f"💸 <b>Solicitar Saque</b>\n\n"
        f"Saldo de comissões: <b>R$ {db_user.affiliate_balance:.2f}</b>\n"
        f"Mínimo: <b>R$ {min_withdraw:.2f}</b>\n\n"
        f"Digite o valor que deseja sacar:\n"
        f"(Depois você informará Pix/dados bancários na etapa segura)",
        reply_markup=back_kb("affiliates"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(WithdrawStates.waiting_amount)
async def process_withdraw_amount(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
):
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = Decimal(raw)
    except Exception:
        await message.answer("❌ Valor inválido.")
        return

    await state.clear()
    try:
        withdraw = await AffiliateService.request_withdraw(
            session, db_user.id, amount
        )
    except ValueError as e:
        await message.answer(f"❌ {e}", reply_markup=affiliates_kb())
        return

    # Link da página web (única parte web do projeto) — preenchido quando o servidor estiver no ar
    web_base = settings.WITHDRAW_WEB_BASE_URL.rstrip("/")
    web_url = f"{web_base}/saque/{withdraw.uuid}"

    await message.answer(
        f"✅ Saque <b>#{withdraw.id}</b> criado: <b>R$ {amount:.2f}</b>\n\n"
        f"Status: <b>Pendente</b>\n\n"
        f"Para concluir, informe seus dados bancários/Pix nesta página segura:\n"
        f"{web_url}\n\n"
        f"(Se a página ainda não estiver no ar, o admin processará manualmente.)",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "affiliate_history")
async def cb_withdraw_history(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    result = await session.execute(
        select(AffiliateWithdraw)
        .where(AffiliateWithdraw.user_id == db_user.id)
        .order_by(AffiliateWithdraw.created_at.desc())
        .limit(15)
    )
    items = list(result.scalars().all())
    min_withdraw = await SettingsService.get_float(session, "affiliate_min_withdraw")

    if not items:
        text = (
            f"📊 <b>HISTÓRICO DE SAQUES</b>\n\n"
            f"Você ainda não solicitou nenhum saque.\n\n"
            f"📉 Saque mínimo atual: <b>R$ {min_withdraw:.2f}</b>"
        )
    else:
        lines = ["📊 <b>HISTÓRICO DE SAQUES</b>\n"]
        for w in items:
            lines.append(
                f"#{w.id} | R$ {w.amount:.2f} | {w.status.value} | "
                f"{w.created_at.strftime('%d/%m/%Y')}"
            )
        text = "\n".join(lines)

    await callback.message.edit_text(
        text, reply_markup=back_kb("affiliates"), parse_mode="HTML"
    )
    await callback.answer()
