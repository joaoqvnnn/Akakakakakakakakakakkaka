"""
Imagem do /start (opcional).
Admin envia foto → salva file_id em welcome_image_file_id.
Pode remover a qualquer momento.
"""

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
    waiting_photo = State()


@router.callback_query(F.data == "admin:welcome_image")
async def cb_welcome_image(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    current = await SettingsService.get(session, "welcome_image_file_id")
    text = (
        "🖼 <b>IMAGEM DO /START</b>\n\n"
        f"Status: <b>{'Com imagem ✅' if current else 'Só texto ⚪'}</b>\n\n"
        "Opcional: se não colocar, o /start manda só a mensagem."
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="📷 Enviar / trocar foto", callback_data="admin:welcome_img_set"
        )
    )
    if current:
        b.row(
            InlineKeyboardButton(
                text="🗑 Remover foto", callback_data="admin:welcome_img_del"
            )
        )
        b.row(
            InlineKeyboardButton(
                text="👁 Ver foto atual", callback_data="admin:welcome_img_view"
            )
        )
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:welcome_img_set")
async def cb_set(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(WelcomeImg.waiting_photo)
    await callback.message.edit_text(
        "📷 Envie a foto do /start agora.\n/cancelar para sair."
    )
    await callback.answer()


@router.message(WelcomeImg.waiting_photo)
async def process_photo(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.")
        return
    if not message.photo:
        await message.answer("❌ Envie uma foto.")
        return
    file_id = message.photo[-1].file_id
    await SettingsService.set(session, "welcome_image_file_id", file_id, db_user.id)
    await state.clear()
    await message.answer("✅ Imagem do /start salva.")


@router.callback_query(F.data == "admin:welcome_img_del")
async def cb_del(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "welcome_image_file_id", "", db_user.id)
    await callback.answer("Removida.", show_alert=True)
    await cb_welcome_image(callback, session, db_user)


@router.callback_query(F.data == "admin:welcome_img_view")
async def cb_view(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    fid = await SettingsService.get(session, "welcome_image_file_id")
    if not fid:
        await callback.answer("Sem imagem.", show_alert=True)
        return
    await callback.message.answer_photo(fid, caption="Imagem atual do /start")
    await callback.answer()
