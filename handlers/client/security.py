import hashlib

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from services.buttons import ButtonService
from keyboards.client_dynamic import profile_kb

router = Router(name="security")


class SecurityStates(StatesGroup):
    set_password = State()
    confirm_password = State()


@router.callback_query(F.data == "set_withdraw_password")
async def cb_set_pwd(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    await state.set_state(SecurityStates.set_password)
    back = await ButtonService.get(session, "btn_back")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=back, callback_data="profile"))
    await callback.message.edit_text(
        "🔐 <b>Senha de saque / liberação</b>\n\n"
        "Digite uma senha (mín. 4 caracteres).\n"
        "Ela será usada no saque e na liberação de produto.",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SecurityStates.set_password)
async def process_set(
    message: Message, state: FSMContext, session: AsyncSession
):
    pwd = (message.text or "").strip()
    if len(pwd) < 4:
        await message.answer("❌ Mínimo 4 caracteres.")
        return
    await state.update_data(pwd=pwd)
    await state.set_state(SecurityStates.confirm_password)
    await message.answer("🔁 Digite a senha novamente para confirmar:")


@router.message(SecurityStates.confirm_password)
async def process_confirm(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    data = await state.get_data()
    await state.clear()
    pwd = (message.text or "").strip()
    if pwd != data.get("pwd"):
        await message.answer(
            "❌ Senhas não conferem.",
            reply_markup=await profile_kb(session),
        )
        return
    db_user.withdraw_password_hash = hashlib.sha256(pwd.encode("utf-8")).hexdigest()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(
        "✅ Senha de segurança salva.",
        reply_markup=await profile_kb(session),
    )
