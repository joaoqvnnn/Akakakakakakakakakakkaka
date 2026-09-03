from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from services.settings_service import SettingsService

router = Router(name="admin_antiflood")


class FloodStates(StatesGroup):
    max_commands = State()
    window = State()
    block_minutes = State()


@router.callback_query(F.data == "admin:cfg_flood")
async def cb_flood(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    max_c = await SettingsService.get(session, "flood_max_commands")
    window = await SettingsService.get(session, "flood_window_seconds")
    block = await SettingsService.get(session, "flood_block_minutes")
    text = (
        f"🛡 <b>ANTI-FLOOD</b>\n\n"
        f"Máx. comandos: <b>{max_c}</b>\n"
        f"Janela (segundos): <b>{window}</b>\n"
        f"Bloqueio (minutos): <b>{block}</b>"
    )
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Máx. comandos", callback_data="admin:flood_max"))
    b.row(InlineKeyboardButton(text="Janela (seg)", callback_data="admin:flood_window"))
    b.row(InlineKeyboardButton(text="Bloqueio (min)", callback_data="admin:flood_block"))
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    await callback.message.edit_text(
        text, reply_markup=b.as_markup(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:flood_max")
async def cb_max(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(FloodStates.max_commands)
    await callback.message.edit_text("Envie o máximo de comandos na janela (ex: 8):")
    await callback.answer()


@router.message(FloodStates.max_commands)
async def p_max(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "flood_max_commands", (message.text or "").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:flood_window")
async def cb_win(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(FloodStates.window)
    await callback.message.edit_text("Janela em segundos (ex: 10):")
    await callback.answer()


@router.message(FloodStates.window)
async def p_win(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "flood_window_seconds", (message.text or "").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:flood_block")
async def cb_block(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(FloodStates.block_minutes)
    await callback.message.edit_text("Minutos de bloqueio após flood (ex: 10):")
    await callback.answer()


@router.message(FloodStates.block_minutes)
async def p_block(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "flood_block_minutes", (message.text or "").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")
