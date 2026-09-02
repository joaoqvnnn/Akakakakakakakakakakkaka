"""
Saque de afiliado via PIX — 100% no Telegram.
Transferência bancária (agência/conta) continua na página web /saque/{uuid}.
"""

from decimal import Decimal

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, AffiliateWithdraw, WithdrawStatus
from keyboards.client import affiliates_kb, main_menu_kb, back_kb
from services.affiliate import AffiliateService
from services.settings_service import SettingsService
from utils.validators import detect_pix_key_type, format_cpf, normalize_phone_br

router = Router(name="withdraw_pix")


class PixWithdrawStates(StatesGroup):
    amount = State()
    key = State()
    password = State()


@router.callback_query(F.data == "affiliate_withdraw")
async def cb_withdraw_menu(callback: CallbackQuery, session: AsyncSession, db_user: User):
    min_w = await SettingsService.get_float(session, "affiliate_min_withdraw")
    can = float(db_user.affiliate_balance) >= min_w

    text = (
        f"💸 <b>Solicitar Saque</b>\n\n"
        f"Saldo comissões: <b>R$ {db_user.affiliate_balance:.2f}</b>\n"
        f"Mínimo: <b>R$ {min_w:.2f}</b>\n\n"
        f"Escolha o método:\n"
        f"• <b>Pix</b> — tudo no Telegram (CPF, telefone, e-mail ou chave)\n"
        f"• <b>Transferência</b> — formulário web (banco, agência, conta)"
    )
    b = InlineKeyboardBuilder()
    if can:
        b.row(
            InlineKeyboardButton(text="💠 Saque via Pix", callback_data="withdraw_pix_start")
        )
        b.row(
            InlineKeyboardButton(
                text="🏦 Transferência bancária (web)",
                callback_data="withdraw_bank_start",
            )
        )
    b.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="affiliates"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "withdraw_pix_start")
async def cb_pix_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    min_w = await SettingsService.get_float(session, "affiliate_min_withdraw")
    if float(db_user.affiliate_balance) < min_w:
        await callback.answer(f"Mínimo R$ {min_w:.2f}", show_alert=True)
        return
    await state.set_state(PixWithdrawStates.amount)
    await callback.message.edit_text(
        f"💠 <b>Saque Pix</b>\n\n"
        f"Saldo: <b>R$ {db_user.affiliate_balance:.2f}</b>\n"
        f"Digite o valor do saque:",
        parse_mode="HTML",
        reply_markup=back_kb("affiliates"),
    )
    await callback.answer()


@router.message(PixWithdrawStates.amount)
async def process_amount(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    try:
        amount = Decimal((message.text or "").replace(",", ".").strip())
    except Exception:
        await message.answer("❌ Valor inválido.")
        return
    min_w = Decimal(str(await SettingsService.get_float(session, "affiliate_min_withdraw")))
    if amount < min_w:
        await message.answer(f"❌ Mínimo R$ {min_w:.2f}")
        return
    if amount > db_user.affiliate_balance:
        await message.answer("❌ Saldo de comissão insuficiente.")
        return

    await state.update_data(amount=str(amount))
    await state.set_state(PixWithdrawStates.key)
    await message.answer(
        "🔑 Envie sua <b>chave Pix</b>:\n\n"
        "• CPF (somente números)\n"
        "• Telefone com DDD\n"
        "• E-mail\n"
        "• Chave aleatória\n\n"
        "O sistema valida o formato.",
        parse_mode="HTML",
    )


@router.message(PixWithdrawStates.key)
async def process_key(message: Message, state: FSMContext, db_user: User):
    key = (message.text or "").strip()
    key_type = detect_pix_key_type(key)
    if not key_type:
        await message.answer(
            "❌ Chave inválida.\n"
            "Use CPF válido, telefone, e-mail ou chave aleatória."
        )
        return

    display = key
    if key_type == "cpf":
        display = format_cpf(key)
    elif key_type == "phone":
        display = normalize_phone_br(key)

    await state.update_data(pix_key=key, pix_key_type=key_type, pix_display=display)
    await state.set_state(PixWithdrawStates.password)
    await message.answer(
        f"Tipo detectado: <b>{key_type}</b>\n"
        f"Chave: <code>{display}</code>\n\n"
        f"🔐 Digite sua <b>senha de saque</b>\n"
        f"(a mesma senha de segurança da conta; se ainda não configurou, "
        f"use a senha de liberação do admin ou peça suporte para criar).",
        parse_mode="HTML",
    )


@router.message(PixWithdrawStates.password)
async def process_password(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    data = await state.get_data()
    await state.clear()
    typed = (message.text or "").strip()

    # Senha: hash do usuário OU senha global de liberação (configurável)
    from services.settings_service import SettingsService
    import hashlib

    ok = False
    if db_user.withdraw_password_hash:
        ok = (
            hashlib.sha256(typed.encode()).hexdigest()
            == db_user.withdraw_password_hash
        )
    else:
        expected = await SettingsService.get(session, "delivery_password")
        ok = typed == expected

    if not ok:
        await message.answer(
            "❌ Senha incorreta. Saque <b>não</b> criado.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        return

    amount = Decimal(data["amount"])
    try:
        withdraw = await AffiliateService.request_withdraw(session, db_user.id, amount)
    except ValueError as e:
        await message.answer(f"❌ {e}")
        return

    withdraw.payment_method = "pix"
    withdraw.pix_key = data["pix_key"]
    withdraw.pix_key_type = data["pix_key_type"]
    withdraw.status = WithdrawStatus.PENDING

    await message.answer(
        f"✅ <b>Saque Pix solicitado</b>\n\n"
        f"ID: <code>{withdraw.uuid}</code>\n"
        f"Valor: <b>R$ {amount:.2f}</b>\n"
        f"Chave ({data['pix_key_type']}): <code>{data['pix_display']}</code>\n"
        f"Status: <b>Pendente</b>\n\n"
        f"O pagamento será processado (Mercado Pago / financeiro). "
        f"Você receberá confirmação quando for pago.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "withdraw_bank_start")
async def cb_bank_start(callback: CallbackQuery, session: AsyncSession, db_user: User):
    """Cria saque e manda só o link web (agência/conta)."""
    min_w = await SettingsService.get_float(session, "affiliate_min_withdraw")
    amount = db_user.affiliate_balance
    if float(amount) < min_w:
        await callback.answer("Saldo insuficiente.", show_alert=True)
        return
    try:
        withdraw = await AffiliateService.request_withdraw(
            session, db_user.id, Decimal(str(amount))
        )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    withdraw.payment_method = "bank_transfer"
    from config import settings

    url = f"{settings.WITHDRAW_WEB_BASE_URL.rstrip('/')}/saque/{withdraw.uuid}"
    await callback.message.edit_text(
        f"🏦 Saque bancário <b>R$ {amount:.2f}</b> criado.\n\n"
        f"Preencha banco, agência e conta nesta página segura:\n"
        f"{url}",
        parse_mode="HTML",
        reply_markup=back_kb("affiliates"),
    )
    await callback.answer()
