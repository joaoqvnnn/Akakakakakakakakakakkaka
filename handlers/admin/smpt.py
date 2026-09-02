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
async def cb_cfg_smtp(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    enabled = await SettingsService.get_bool(session, "smtp_enabled")
    host = await SettingsService.get(session, "smtp_host")
    port = await SettingsService.get(session, "smtp_port")
    user = await SettingsService.get(session, "smtp_user")
    from_addr = await SettingsService.get(session, "smtp_from")

    text = (
        f"<b>E-MAIL SMTP (entrega da compra)</b>\n\n"
        f"Status: <b>{'ON 🟢' if enabled else 'OFF 🔴'}</b>\n"
        f"Host: <code>{host or '—'}</code>\n"
        f"Porta: <code>{port}</code>\n"
        f"User: <code>{user or '—'}</code>\n"
        f"From: <code>{from_addr or '—'}</code>\n\n"
        f"Quando ativo, o bot envia o modelo "
        f"<code>delivery_email</code> para o cliente."
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=f"SMTP ({'ON' if enabled else 'OFF'})",
            callback_data="admin:smtp_toggle",
        )
    )
    b.row(InlineKeyboardButton(text="Host", callback_data="admin:smtp_host"))
    b.row(InlineKeyboardButton(text="Porta", callback_data="admin:smtp_port"))
    b.row(InlineKeyboardButton(text="Usuário", callback_data="admin:smtp_user"))
    b.row(InlineKeyboardButton(text="Senha", callback_data="admin:smtp_password"))
    b.row(InlineKeyboardButton(text="From (remetente)", callback_data="admin:smtp_from"))
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:smtp_toggle")
async def cb_smtp_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    cur = await SettingsService.get_bool(session, "smtp_enabled")
    await SettingsService.set(session, "smtp_enabled", "false" if cur else "true", db_user.id)
    await cb_cfg_smtp(callback, session, db_user)


@router.callback_query(F.data == "admin:smtp_host")
async def cb_host(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(SmtpStates.host)
    await callback.message.edit_text("Envie o host SMTP (ex: smtp.gmail.com):")
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
    await callback.message.edit_text("Envie a porta (ex: 587):")
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
    await callback.message.edit_text("Envie o usuário SMTP:")
    await callback.answer()


@router.message(SmtpStates.user)
async def p_user(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "smtp_user", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Usuário salvo.")


@router.callback_query(F.data == "admin:smtp_password")
async def cb_pass(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(SmtpStates.password)
    await callback.message.edit_text("Envie a senha SMTP:")
    await callback.answer()


@router.message(SmtpStates.password)
async def p_pass(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "smtp_password", (message.text or "").strip(), db_user.id)
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ Senha SMTP salva.")


@router.callback_query(F.data == "admin:smtp_from")
async def cb_from(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(SmtpStates.from_addr)
    await callback.message.edit_text("Envie o e-mail remetente (From):")
    await callback.answer()


@router.message(SmtpStates.from_addr)
async def p_from(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "smtp_from", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ From salvo.")
