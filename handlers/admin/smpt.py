from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from services.settings_service import SettingsService

router = Router(name="admin_smtp")


class SmtpStates(StatesGroup):
    host = State()
    port = State()
    user = State()
    password = State()
    from_addr = State()


@router.callback_query(F.data == "admin:cfg_smtp")
async def cb_smtp(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    enabled = await SettingsService.get_bool(session, "smtp_enabled")
    host = await SettingsService.get(session, "smtp_host")
    port = await SettingsService.get(session, "smtp_port")
    user = await SettingsService.get(session, "smtp_user")
    frm = await SettingsService.get(session, "smtp_from")
    tls = await SettingsService.get_bool(session, "smtp_use_tls")

    text = (
        f"📧 <b>E-MAIL SMTP</b>\n\n"
        f"Status: <b>{'ON' if enabled else 'OFF'}</b>\n"
        f"Host: <code>{host or '—'}</code>\n"
        f"Porta: <code>{port or '—'}</code>\n"
        f"User: <code>{user or '—'}</code>\n"
        f"From: <code>{frm or '—'}</code>\n"
        f"TLS: <b>{'sim' if tls else 'não'}</b>"
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=f"{'🔴 Desativar' if enabled else '🟢 Ativar'}",
            callback_data="admin:smtp_toggle",
        )
    )
    b.row(InlineKeyboardButton(text="Host", callback_data="admin:smtp_host"))
    b.row(InlineKeyboardButton(text="Porta", callback_data="admin:smtp_port"))
    b.row(InlineKeyboardButton(text="Usuário", callback_data="admin:smtp_user"))
    b.row(InlineKeyboardButton(text="Senha", callback_data="admin:smtp_password"))
    b.row(InlineKeyboardButton(text="From", callback_data="admin:smtp_from"))
    b.row(
        InlineKeyboardButton(
            text=f"TLS ({'ON' if tls else 'OFF'})",
            callback_data="admin:smtp_tls",
        )
    )
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:smtp_toggle")
async def cb_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    cur = await SettingsService.get_bool(session, "smtp_enabled")
    await SettingsService.set(session, "smtp_enabled", "0" if cur else "1", db_user.id)
    await cb_smtp(callback, session, db_user)


@router.callback_query(F.data == "admin:smtp_tls")
async def cb_tls(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    cur = await SettingsService.get_bool(session, "smtp_use_tls")
    await SettingsService.set(session, "smtp_use_tls", "0" if cur else "1", db_user.id)
    await cb_smtp(callback, session, db_user)


@router.callback_query(F.data == "admin:smtp_host")
async def cb_host(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(SmtpStates.host)
    await callback.message.edit_text("Host SMTP (ex: smtp.gmail.com):")
    await callback.answer()


@router.message(SmtpStates.host)
async def p_host(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "smtp_host", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Host salvo.")


@router.callback_query(F.data == "admin:smtp_port")
async def cb_port(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(SmtpStates.port)
    await callback.message.edit_text("Porta (ex: 587):")
    await callback.answer()


@router.message(SmtpStates.port)
async def p_port(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "smtp_port", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Porta salva.")


@router.callback_query(F.data == "admin:smtp_user")
async def cb_user(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(SmtpStates.user)
    await callback.message.edit_text("Usuário SMTP:")
    await callback.answer()


@router.message(SmtpStates.user)
async def p_user(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "smtp_user", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Usuário salvo.")


@router.callback_query(F.data == "admin:smtp_password")
async def cb_password(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(SmtpStates.password)
    await callback.message.edit_text("Senha SMTP:")
    await callback.answer()


@router.message(SmtpStates.password)
async def p_password(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "smtp_password", (message.text or "").strip(), db_user.id)
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ Senha salva.")


@router.callback_query(F.data == "admin:smtp_from")
async def cb_from(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(SmtpStates.from_addr)
    await callback.message.edit_text("E-mail remetente (From):")
    await callback.answer()


@router.message(SmtpStates.from_addr)
async def p_from(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "smtp_from", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ From salvo.")
