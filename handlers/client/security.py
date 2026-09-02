import hashlib

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from keyboards.client import profile_kb, main_menu_kb

router = Router(name="security")


class SecurityStates(StatesGroup):
    set_password = State()
    confirm_password = State()


def _hash(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()


@router.callback_query(F.data == "security_password")
async def cb_security(callback: CallbackQuery, db_user: User):
    has = bool(db_user.withdraw_password_hash)
    text = (
        "🔐 <b>Senha de saque / segurança</b>\n\n"
        f"Status: <b>{'Definida ✅' if has else 'Não definida ❌'}</b>\n\n"
        "Usada no saque Pix de afiliado.\n"
        "Nunca compartilhe essa senha."
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✏️ Definir / alterar senha", callback_data="security_set_pwd"
        )
    )
    b.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="profile"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "security_set_pwd")
async def cb_set_pwd(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SecurityStates.set_password)
    await callback.message.edit_text(
        "🔐 Digite a nova senha de saque (mín. 4 caracteres):\n"
        "/cancelar para sair."
    )
    await callback.answer()


@router.message(SecurityStates.set_password)
async def process_set_pwd(message: Message, state: FSMContext):
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.", reply_markup=main_menu_kb())
        return
    pwd = (message.text or "").strip()
    if len(pwd) < 4:
        await message.answer("❌ Mínimo 4 caracteres.")
        return
    await state.update_data(pwd=pwd)
    await state.set_state(SecurityStates.confirm_password)
    await message.answer("Repita a senha:")


@router.message(SecurityStates.confirm_password)
async def process_confirm_pwd(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    data = await state.get_data()
    await state.clear()
    if (message.text or "").strip() != data.get("pwd"):
        await message.answer("❌ Senhas não conferem.", reply_markup=profile_kb())
        return
    db_user.withdraw_password_hash = _hash(data["pwd"])
    await message.answer(
        "✅ Senha de saque salva com sucesso.",
        reply_markup=profile_kb(),
    )
