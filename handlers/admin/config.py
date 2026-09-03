from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from keyboards.admin import (
    admin_cfg_general_kb,
    admin_cfg_admins_kb,
    admin_cfg_affiliate_kb,
    admin_cfg_users_kb,
    admin_cfg_pix_kb,
    admin_config_kb,
)
from services.settings_service import SettingsService

router = Router(name="admin_config")


class CfgStates(StatesGroup):
    support = State()
    separator = State()
    logs_chat = State()
    adm_add = State()
    adm_remove = State()
    points_recharge = State()
    points_min = State()
    multiplier = State()
    commission = State()
    min_withdraw = State()
    reg_bonus = State()
    pix_token = State()
    pix_min = State()
    pix_max = State()
    pix_exp = State()
    pix_bonus = State()
    pix_bonus_min = State()
    baileys_url = State()
    baileys_key = State()
    delivery_pwd = State()
    user_search = State()


# ---------- GERAL ----------
@router.callback_query(F.data == "admin:cfg_general")
async def cb_general(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    support = await SettingsService.get(session, "support_link")
    sep = await SettingsService.get(session, "separator")
    logs = await SettingsService.get(session, "logs_chat_id")
    maint = await SettingsService.get_bool(session, "maintenance_mode")
    text = (
        f"⚙️ <b>CONFIGURAÇÕES GERAIS</b>\n\n"
        f"DESTINO DAS LOG'S: <code>{logs or '—'}</code>\n"
        f"LINK DO SUPORTE: {support or '—'}\n"
        f"SEPARADOR: <code>{sep}</code>\n"
        f"MANUTENÇÃO: <b>{'ON' if maint else 'OFF'}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_general_kb(maint), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:set_support")
async def cb_set_support(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.support)
    await callback.message.edit_text("🔗 Envie o novo link de suporte:")
    await callback.answer()


@router.message(CfgStates.support)
async def p_support(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "support_link", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Suporte atualizado.")


@router.callback_query(F.data == "admin:set_separator")
async def cb_set_sep(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.separator)
    await callback.message.edit_text("📌 Envie o novo separador (ex: ===):")
    await callback.answer()


@router.message(CfgStates.separator)
async def p_sep(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "separator", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Separador atualizado.")


@router.callback_query(F.data == "admin:set_logs_chat")
async def cb_set_logs(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.logs_chat)
    await callback.message.edit_text("📨 Envie o ID do chat de logs (ex: -100...):")
    await callback.answer()


@router.message(CfgStates.logs_chat)
async def p_logs(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "logs_chat_id", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Destino de logs atualizado.")


@router.callback_query(F.data == "admin:toggle_maintenance")
async def cb_maint(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    current = await SettingsService.get_bool(session, "maintenance_mode")
    await SettingsService.set(
        session, "maintenance_mode", "0" if current else "1", db_user.id
    )
    await cb_general(callback, session, db_user)


# ---------- ADMINS ----------
@router.callback_query(F.data == "admin:cfg_admins")
async def cb_admins(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    result = await session.execute(select(User).where(User.is_admin.is_(True)))
    admins = list(result.scalars().all())
    text = f"👑 <b>PAINEL CONFIGURAR ADMIN</b>\n\nAdministradores: <b>{len(admins)}</b>"
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_admins_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:adm_add")
async def cb_adm_add(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.adm_add)
    await callback.message.edit_text("➕ Envie o ID Telegram do novo admin:")
    await callback.answer()


@router.message(CfgStates.adm_add)
async def p_adm_add(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ ID inválido.")
        return
    user = await session.get(User, uid)
    if not user:
        user = User(id=uid, is_admin=True)
        session.add(user)
    else:
        user.is_admin = True
    await state.clear()
    await message.answer(f"✅ Admin {uid} adicionado.")


@router.callback_query(F.data == "admin:adm_remove")
async def cb_adm_remove(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.adm_remove)
    await callback.message.edit_text("➖ Envie o ID do admin para remover:")
    await callback.answer()


@router.message(CfgStates.adm_remove)
async def p_adm_remove(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ ID inválido.")
        return
    user = await session.get(User, uid)
    if user:
        user.is_admin = False
    await state.clear()
    await message.answer(f"✅ Admin {uid} removido (flag).")


@router.callback_query(F.data == "admin:adm_list")
async def cb_adm_list(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    result = await session.execute(select(User).where(User.is_admin.is_(True)))
    admins = list(result.scalars().all())
    lines = ["📋 <b>Lista de ADM</b>\n"]
    for a in admins:
        lines.append(f"• <code>{a.id}</code> — {a.first_name or a.username or '—'}")
    if len(lines) == 1:
        lines.append("Nenhum.")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg_admins"))
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=b.as_markup(), parse_mode="HTML"
    )
    await callback.answer()


# ---------- AFILIADOS ----------
@router.callback_query(F.data == "admin:cfg_affiliate")
async def cb_aff(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    enabled = await SettingsService.get_bool(session, "affiliate_enabled")
    pts = await SettingsService.get(session, "points_per_recharge")
    min_c = await SettingsService.get(session, "points_min_convert")
    mult = await SettingsService.get(session, "points_multiplier")
    com = await SettingsService.get(session, "affiliate_commission_percent")
    min_w = await SettingsService.get(session, "affiliate_min_withdraw")
    text = (
        f"🤝 <b>CONFIGURAR AFILIADOS</b>\n\n"
        f"Sistema: <b>{'ON' if enabled else 'OFF'}</b>\n"
        f"Pontos por recarga: <b>{pts}</b>\n"
        f"Pontos mín. converter: <b>{min_c}</b>\n"
        f"Multiplicador: <b>{mult}</b>\n"
        f"Comissão %: <b>{com}</b>\n"
        f"Saque mínimo: <b>R$ {min_w}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_affiliate_kb(enabled), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:aff_toggle")
async def cb_aff_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    cur = await SettingsService.get_bool(session, "affiliate_enabled")
    await SettingsService.set(session, "affiliate_enabled", "0" if cur else "1", db_user.id)
    await cb_aff(callback, session, db_user)


async def _set_num_state(callback, state, st, prompt):
    await state.set_state(st)
    await callback.message.edit_text(prompt)
    await callback.answer()


@router.callback_query(F.data == "admin:aff_points_recharge")
async def cb_pts_r(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await _set_num_state(callback, state, CfgStates.points_recharge, "⭐ Pontos por recarga:")


@router.message(CfgStates.points_recharge)
async def p_pts_r(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "points_per_recharge", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_points_min")
async def cb_pts_m(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await _set_num_state(callback, state, CfgStates.points_min, "📉 Pontos mínimos para converter:")


@router.message(CfgStates.points_min)
async def p_pts_m(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "points_min_convert", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_multiplier")
async def cb_mult(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await _set_num_state(callback, state, CfgStates.multiplier, "✖️ Multiplicador (ex: 0.01):")


@router.message(CfgStates.multiplier)
async def p_mult(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "points_multiplier", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_commission")
async def cb_com(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await _set_num_state(callback, state, CfgStates.commission, "💰 Comissão % (ex: 20):")


@router.message(CfgStates.commission)
async def p_com(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "affiliate_commission_percent", (message.text or "").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_min_withdraw")
async def cb_min_w(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await _set_num_state(callback, state, CfgStates.min_withdraw, "💸 Saque mínimo R$:")


@router.message(CfgStates.min_withdraw)
async def p_min_w(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "affiliate_min_withdraw", (message.text or "").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


# ---------- USERS ----------
@router.callback_query(F.data == "admin:cfg_users")
async def cb_users(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    bonus = await SettingsService.get(session, "register_bonus")
    text = (
        f"👥 <b>CONFIGURAR USUÁRIOS</b>\n\n"
        f"Bônus de registro atual: <b>R$ {bonus}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_users_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:set_reg_bonus")
async def cb_reg_bonus(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.reg_bonus)
    await callback.message.edit_text("🎁 Novo bônus de registro (R$):")
    await callback.answer()


@router.message(CfgStates.reg_bonus)
async def p_reg_bonus(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "register_bonus", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:user_search")
async def cb_user_search(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.user_search)
    await callback.message.edit_text("🔎 Envie o ID Telegram do usuário:")
    await callback.answer()


@router.message(CfgStates.user_search)
async def p_user_search(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await state.clear()
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ ID inválido.")
        return
    user = await session.get(User, uid)
    if not user:
        await message.answer("❌ Usuário não encontrado.")
        return
    from keyboards.admin import admin_user_actions_kb

    text = (
        f"👤 <b>Usuário</b> <code>{user.id}</code>\n"
        f"Nome: {user.first_name or '—'}\n"
        f"User: @{user.username or '—'}\n"
        f"Saldo: R$ {user.balance:.2f}\n"
        f"Gasto: R$ {user.total_spent:.2f}\n"
        f"Depositado: R$ {user.total_deposited:.2f}\n"
        f"Bloqueado: {'Sim' if user.is_blocked else 'Não'}"
    )
    await message.answer(
        text, reply_markup=admin_user_actions_kb(user.id), parse_mode="HTML"
    )


# ---------- PIX ----------
@router.callback_query(F.data == "admin:cfg_pix")
async def cb_pix(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    token = await SettingsService.get(session, "mp_access_token")
    masked = (token[:8] + "…") if token and len(token) > 8 else (token or "não configurado")
    text = (
        f"💠 <b>CONFIGURAR PIX</b>\n\n"
        f"Token MP: <code>{masked}</code>\n"
        f"Mín: R$ {await SettingsService.get(session, 'pix_min')}\n"
        f"Máx: R$ {await SettingsService.get(session, 'pix_max')}\n"
        f"Expiração: {await SettingsService.get(session, 'pix_expiration_minutes')} min\n"
        f"Bônus: {await SettingsService.get(session, 'bonus_percent')}%\n"
        f"Mín bônus: R$ {await SettingsService.get(session, 'bonus_min_value')}"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_pix_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:pix_token")
async def cb_pix_token(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.pix_token)
    await callback.message.edit_text("🔑 Envie o Access Token do Mercado Pago:")
    await callback.answer()


@router.message(CfgStates.pix_token)
async def p_pix_token(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "mp_access_token", (message.text or "").strip(), db_user.id)
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ Token salvo.")


@router.callback_query(F.data == "admin:pix_min")
async def cb_pix_min(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.pix_min)
    await callback.message.edit_text("⬇️ Depósito mínimo:")
    await callback.answer()


@router.message(CfgStates.pix_min)
async def p_pix_min(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "pix_min", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_max")
async def cb_pix_max(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.pix_max)
    await callback.message.edit_text("⬆️ Depósito máximo:")
    await callback.answer()


@router.message(CfgStates.pix_max)
async def p_pix_max(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "pix_max", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_exp")
async def cb_pix_exp(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.pix_exp)
    await callback.message.edit_text("⏱ Minutos de expiração do PIX:")
    await callback.answer()


@router.message(CfgStates.pix_exp)
async def p_pix_exp(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "pix_expiration_minutes", (message.text or "").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_bonus")
async def cb_pix_bonus(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.pix_bonus)
    await callback.message.edit_text("🎁 Bônus % de depósito:")
    await callback.answer()


@router.message(CfgStates.pix_bonus)
async def p_pix_bonus(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "bonus_percent", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_bonus_min")
async def cb_pix_bonus_min(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.pix_bonus_min)
    await callback.message.edit_text("📌 Valor mínimo para ganhar bônus:")
    await callback.answer()


@router.message(CfgStates.pix_bonus_min)
async def p_pix_bonus_min(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "bonus_min_value", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


# ---------- BAILEYS / SENHA ENTREGA ----------
@router.callback_query(F.data == "admin:cfg_delivery")
async def cb_delivery(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    enabled = await SettingsService.get_bool(session, "baileys_enabled")
    url = await SettingsService.get(session, "baileys_api_url")
    pwd_on = await SettingsService.get_bool(session, "delivery_password_enabled")
    text = (
        f"📲 <b>ENTREGA WHATSAPP (BAILEYS)</b>\n\n"
        f"Baileys: <b>{'ON' if enabled else 'OFF'}</b>\n"
        f"URL: <code>{url or '—'}</code>\n"
        f"Senha liberação: <b>{'ON' if pwd_on else 'OFF'}</b>"
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=f"Baileys ({'ON' if enabled else 'OFF'})",
            callback_data="admin:baileys_toggle",
        )
    )
    b.row(InlineKeyboardButton(text="URL API", callback_data="admin:baileys_url"))
    b.row(InlineKeyboardButton(text="API Key", callback_data="admin:baileys_key"))
    b.row(
        InlineKeyboardButton(
            text=f"Senha liberação ({'ON' if pwd_on else 'OFF'})",
            callback_data="admin:delivery_pwd_toggle",
        )
    )
    b.row(InlineKeyboardButton(text="Definir senha", callback_data="admin:delivery_pwd_set"))
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:baileys_toggle")
async def cb_bail_tog(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    cur = await SettingsService.get_bool(session, "baileys_enabled")
    await SettingsService.set(session, "baileys_enabled", "0" if cur else "1", db_user.id)
    await cb_delivery(callback, session, db_user)


@router.callback_query(F.data == "admin:baileys_url")
async def cb_bail_url(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.baileys_url)
    await callback.message.edit_text("URL base da API Baileys:")
    await callback.answer()


@router.message(CfgStates.baileys_url)
async def p_bail_url(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "baileys_api_url", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:baileys_key")
async def cb_bail_key(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.baileys_key)
    await callback.message.edit_text("API Key Baileys:")
    await callback.answer()


@router.message(CfgStates.baileys_key)
async def p_bail_key(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "baileys_api_key", (message.text or "").strip(), db_user.id)
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:delivery_pwd_toggle")
async def cb_pwd_tog(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    cur = await SettingsService.get_bool(session, "delivery_password_enabled")
    await SettingsService.set(
        session, "delivery_password_enabled", "0" if cur else "1", db_user.id
    )
    await cb_delivery(callback, session, db_user)


@router.callback_query(F.data == "admin:delivery_pwd_set")
async def cb_pwd_set(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.delivery_pwd)
    await callback.message.edit_text("🔐 Nova senha global de liberação:")
    await callback.answer()


@router.message(CfgStates.delivery_pwd)
async def p_pwd(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "delivery_password", (message.text or "").strip(), db_user.id)
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ Senha de liberação atualizada.")
