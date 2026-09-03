from decimal import Decimal

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from services.affiliate import AffiliateService
from services.settings_service import SettingsService
from services.buttons import ButtonService
from services.order_secure_link import OrderSecureService
from keyboards.client_dynamic import affiliates_kb, main_menu_kb
from utils.validators import detect_pix_key_type
from config import settings

router = Router(name="withdraw_pix")


class PixWithdrawStates(StatesGroup):
    amount = State()
    key = State()
    password = State()


@router.callback_query(F.data == "affiliate_withdraw")
async def cb_withdraw(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
):
    min_w = await SettingsService.get_float(session, "affiliate_min_withdraw")
    if float(db_user.affiliate_balance or 0) < min_w:
        await callback.answer(
            f"Saldo insuficiente. Mínimo R$ {min_w:.2f}", show_alert=True
        )
        return

    back = await ButtonService.get(session, "btn_back")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=back, callback_data="affiliates"))

    web_base = getattr(settings, "WITHDRAW_WEB_BASE_URL", "") or ""
    text = (
        f"💸 <b>Solicitar saque</b>\n\n"
        f"Saldo de comissões: <b>R$ {db_user.affiliate_balance:.2f}</b>\n"
        f"Mínimo: <b>R$ {min_w:.2f}</b>\n\n"
        f"Digite o <b>valor</b> do saque:\n"
        f"(ou use o site bancário se preferir TED)"
    )
    if web_base:
        text += f"\n\n🏦 Transferência bancária:\n{web_base}/login"

    await state.set_state(PixWithdrawStates.amount)
    await callback.message.edit_text(
        text, reply_markup=b.as_markup(), parse_mode="HTML"
    )
    await callback.answer()


@router.message(PixWithdrawStates.amount)
async def process_amount(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    try:
        amount = Decimal((message.text or "").replace(",", ".").strip())
    except Exception:
        await message.answer("❌ Valor inválido.")
        return

    min_w = Decimal(
        str(await SettingsService.get(session, "affiliate_min_withdraw") or "20")
    )
    if amount < min_w:
        await message.answer(f"❌ Mínimo R$ {min_w:.2f}")
        return
    if amount > (db_user.affiliate_balance or Decimal("0")):
        await message.answer("❌ Saldo de comissão insuficiente.")
        return

    await state.update_data(amount=str(amount))
    await state.set_state(PixWithdrawStates.key)
    await message.answer(
        "💠 Digite sua <b>chave PIX</b> (CPF, e-mail, telefone ou aleatória):",
        parse_mode="HTML",
    )


@router.message(PixWithdrawStates.key)
async def process_key(message: Message, state: FSMContext):
    key = (message.text or "").strip()
    if len(key) < 5:
        await message.answer("❌ Chave inválida.")
        return
    await state.update_data(pix_key=key, key_type=detect_pix_key_type(key))
    await state.set_state(PixWithdrawStates.password)
    await message.answer(
        "🔐 Digite sua <b>senha de saque</b> (cadastrada no Telegram):",
        parse_mode="HTML",
    )


@router.message(PixWithdrawStates.password)
async def process_password(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    data = await state.get_data()
    await state.clear()
    password = (message.text or "").strip()

    fallback = await SettingsService.get(session, "delivery_password") or "1234"
    if not OrderSecureService.check_user_password(db_user, password, fallback):
        await message.answer(
            "❌ Senha incorreta.",
            reply_markup=await affiliates_kb(session, True),
        )
        return

    amount = Decimal(data["amount"])
    try:
        w = await AffiliateService.request_withdraw(session, db_user.id, amount)
        w.payment_method = "pix"
        w.pix_key = data.get("pix_key")
        w.pix_key_type = data.get("key_type")
        await session.flush()
    except ValueError as e:
        await message.answer(str(e), reply_markup=await main_menu_kb(session))
        return

    await message.answer(
        f"✅ Saque de <b>R$ {amount:.2f}</b> solicitado.\n"
        f"ID: <code>{w.uuid}</code>\n"
        f"Status: <b>PENDENTE</b>\n\n"
        f"O admin processará o Pix. Você será notificado.",
        parse_mode="HTML",
        reply_markup=await main_menu_kb(session),
    )
