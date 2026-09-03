from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from services.settings_service import SettingsService

router = Router(name="admin_web_password")


class WebPwdStates(StatesGroup):
    waiting = State()


@router.callback_query(F.data == "admin:web_password")
async def cb_web_password(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    current = await SettingsService.get(session, "web_withdraw_password") or "Larizinha@2026"
    text = (
        "🔐 <b>SENHA DO SITE DE SAQUE</b>\n\n"
        f"Senha atual: <code>{current}</code>\n\n"
        "É a senha da página web antes de preencher banco/agência/conta.\n"
        "Diferente da senha de saque do cliente no Telegram."
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✏️ Alterar senha do site",
            callback_data="admin:web_pwd_set",
        )
    )
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:web_pwd_set")
async def cb_set(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(WebPwdStates.waiting)
    await callback.message.edit_text("🔐 Envie a nova senha de acesso ao site de saque:")
    await callback.answer()


@router.message(WebPwdStates.waiting)
async def process_pwd(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    pwd = (message.text or "").strip()
    if len(pwd) < 4:
        await message.answer("❌ Mínimo 4 caracteres.")
        return
    await SettingsService.set(session, "web_withdraw_password", pwd, db_user.id)
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ Senha do site de saque atualizada.")
