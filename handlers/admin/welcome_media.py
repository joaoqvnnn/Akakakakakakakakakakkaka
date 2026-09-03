from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from services.settings_service import SettingsService

router = Router(name="admin_welcome_media")


class WelcomeImg(StatesGroup):
    waiting = State()


@router.callback_query(F.data == "admin:welcome_image")
async def cb_welcome(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    has = await SettingsService.get(session, "welcome_image_file_id")
    text = (
        "🖼 <b>IMAGEM DO /start</b>\n\n"
        f"Status: <b>{'configurada' if has else 'não configurada'}</b>\n\n"
        "Essa foto aparece junto com a mensagem de boas-vindas."
    )
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📷 Enviar/trocar", callback_data="admin:welcome_img_set"))
    if has:
        b.row(InlineKeyboardButton(text="👁 Ver atual", callback_data="admin:welcome_img_view"))
        b.row(InlineKeyboardButton(text="🗑 Remover", callback_data="admin:welcome_img_del"))
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:welcome_img_set")
async def cb_set(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(WelcomeImg.waiting)
    await callback.message.edit_text("📷 Envie a foto do /start:")
    await callback.answer()


@router.message(WelcomeImg.waiting)
async def process(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    if not message.photo:
        await message.answer("❌ Envie uma foto.")
        return
    await state.clear()
    await SettingsService.set(
        session, "welcome_image_file_id", message.photo[-1].file_id, db_user.id
    )
    await message.answer("✅ Imagem do /start salva.")


@router.callback_query(F.data == "admin:welcome_img_view")
async def cb_view(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    file_id = await SettingsService.get(session, "welcome_image_file_id")
    if not file_id:
        await callback.answer("Sem imagem.", show_alert=True)
        return
    await callback.message.answer_photo(file_id, caption="Imagem atual do /start")
    await callback.answer()


@router.callback_query(F.data == "admin:welcome_img_del")
async def cb_del(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "welcome_image_file_id", "", db_user.id)
    await callback.answer("Removida.")
    await cb_welcome(callback, session, db_user)
