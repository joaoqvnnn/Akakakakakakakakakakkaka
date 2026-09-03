import secrets
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from keyboards.admin import admin_giftcards_kb
from services.giftcard import GiftCardService

router = Router(name="admin_giftcards")


class GiftStates(StatesGroup):
    value = State()
    code = State()
    days = State()


@router.callback_query(F.data == "admin:gift_create")
async def cb_create(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    await state.set_state(GiftStates.value)
    await callback.message.edit_text("🎁 Valor do gift card (ex: 10.00):")
    await callback.answer()


@router.message(GiftStates.value)
async def process_value(message: Message, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    try:
        value = Decimal((message.text or "").replace(",", ".").strip())
        if value <= 0:
            raise ValueError
    except Exception:
        await message.answer("❌ Valor inválido.")
        return
    await state.update_data(value=str(value))
    await state.set_state(GiftStates.code)
    await message.answer(
        "Código do gift:\n"
        "• Envie um código customizado, ou\n"
        "• Envie <code>auto</code> para gerar automaticamente.",
        parse_mode="HTML",
    )


@router.message(GiftStates.code)
async def process_code(message: Message, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    raw = (message.text or "").strip()
    code = secrets.token_hex(4).upper() if raw.lower() == "auto" else raw.upper()
    await state.update_data(code=code)
    await state.set_state(GiftStates.days)
    await message.answer(
        "Validade em dias (0 = sem expiração):"
    )


@router.message(GiftStates.days)
async def process_days(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    try:
        days = int((message.text or "0").strip())
    except Exception:
        await message.answer("❌ Número inválido.")
        return
    data = await state.get_data()
    await state.clear()
    expires = None
    if days > 0:
        expires = datetime.now(timezone.utc) + timedelta(days=days)
    try:
        gift = await GiftCardService.create(
            session,
            code=data["code"],
            value=Decimal(data["value"]),
            admin_id=db_user.id,
            max_uses=1,
            expires_at=expires,
        )
    except ValueError as e:
        await message.answer(f"❌ {e}", reply_markup=admin_giftcards_kb())
        return
    await message.answer(
        f"✅ Gift criado!\n"
        f"Código: <code>{gift.code}</code>\n"
        f"Valor: <b>R$ {gift.value:.2f}</b>\n"
        f"Validade: {expires.strftime('%d/%m/%Y') if expires else 'sem expiração'}",
        parse_mode="HTML",
        reply_markup=admin_giftcards_kb(),
    )
