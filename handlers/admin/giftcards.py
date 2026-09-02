from decimal import Decimal
from datetime import datetime, timedelta, timezone
import secrets
import string

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from keyboards.admin import admin_giftcards_kb, admin_back_kb
from services.giftcard import GiftCardService

router = Router(name="admin_giftcards")


class GiftCreate(StatesGroup):
    value = State()
    code = State()


@router.callback_query(F.data == "admin:gift_create")
async def cb_gift_create(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(GiftCreate.value)
    await callback.message.edit_text(
        "🎁 <b>Criar Gift Card</b>\n\nEnvie o valor (ex: 20 ou 50.00):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(GiftCreate.value)
async def process_gift_value(message: Message, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    try:
        value = Decimal((message.text or "").replace(",", "."))
        if value <= 0:
            raise ValueError
    except Exception:
        await message.answer("❌ Valor inválido.")
        return
    await state.update_data(value=str(value))
    await state.set_state(GiftCreate.code)
    await message.answer(
        "Envie o código desejado\nou envie <code>auto</code> para gerar automaticamente:",
        parse_mode="HTML",
    )


@router.message(GiftCreate.code)
async def process_gift_code(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    data = await state.get_data()
    await state.clear()
    raw = (message.text or "").strip()
    if raw.lower() == "auto":
        alphabet = string.ascii_uppercase + string.digits
        code = "".join(secrets.choice(alphabet) for _ in range(12))
    else:
        code = raw.upper()

    value = Decimal(data["value"])
    expires = datetime.now(timezone.utc) + timedelta(days=90)

    gift = await GiftCardService.create(
        session,
        code=code,
        value=value,
        admin_id=db_user.id,
        max_uses=1,
        expires_at=expires,
    )
    await message.answer(
        f"✅ Gift Card criado!\n\n"
        f"Código: <code>{gift.code}</code>\n"
        f"Valor: <b>R$ {gift.value:.2f}</b>\n"
        f"Validade: 90 dias",
        parse_mode="HTML",
        reply_markup=admin_giftcards_kb(),
    )
