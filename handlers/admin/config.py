from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, AdminLog
from keyboards.admin import (
    admin_config_kb,
    admin_cfg_general_kb,
    admin_cfg_admins_kb,
    admin_cfg_affiliate_kb,
    admin_cfg_users_kb,
    admin_cfg_pix_kb,
    admin_back_kb,
    admin_giftcards_kb,
    admin_payments_kb,
)
from handlers.admin.panel import is_admin
from services.settings_service import SettingsService

router = Router(name="admin_config")


class CfgStates(StatesGroup):
    support = State()
    separator = State()
    logs_chat = State()
    adm_add = State()
    adm_remove = State()
    aff_points = State()
    aff_min = State()
    aff_mult = State()
    aff_commission = State()
    aff_min_withdraw = State()
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


@router.callback_query(F.data == "admin:cfg")
async def cb_cfg(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    text = (
        "<b>MENU DE CONFIGURAÇÕES DO BOT</b>\n\n"
        f"Admin: <b>Sim</b>\n"
        f"Dono: <b>{'Sim' if db_user.id in settings.ADMIN_IDS else 'Não'}</b>\n\n"
        "Escolha o que deseja configurar:"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_config_kb(), parse_mode="HTML"
    )
    await callback.answer()


# ========== GERAIS ==========

@router.callback_query(F.data == "admin:cfg_general")
async def cb_cfg_general(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    logs = await SettingsService.get(session, "logs_chat_id")
    support = await SettingsService.get(session, "support_link")
    sep = await SettingsService.get(session, "separator")
    maint = await SettingsService.get_bool(session, "maintenance_mode")
    text = (
        "<b>CONFIGURAÇÕES GERAIS</b>\n\n"
        f"DESTINO DAS LOG'S: <code>{logs or 'não definido'}</code>\n"
        f"LINK DO SUPORTE: {support}\n"
        f"SEPARADOR: <code>{sep}</code>\n\n"
        f"Ex separador: <code>NOME{sep}VALOR</code>"
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
    await callback.message.edit_text("🔗 Envie o link de suporte:")
    await callback.answer()


@router.message(CfgStates.support)
async def process_support(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
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
    await callback.message.edit_text("📌 Envie o separador (ex: ===):")
    await callback.answer()


@router.message(CfgStates.separator)
async def process_sep(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    sep = (message.text or "").strip()
    if not sep:
        await message.answer("❌ Inválido.")
        return
    await SettingsService.set(session, "separator", sep, db_user.id)
    await state.clear()
    await message.answer(f"✅ Separador: <code>{sep}</code>", parse_mode="HTML")


@router.callback_query(F.data == "admin:set_logs_chat")
async def cb_set_logs(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.logs_chat)
    await callback.message.edit_text("📨 ID do chat/canal de logs:")
    await callback.answer()


@router.message(CfgStates.logs_chat)
async def process_logs(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "logs_chat_id", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Destino de logs salvo.")


@router.callback_query(F.data == "admin:toggle_maintenance")
async def cb_toggle_maint(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    current = await SettingsService.get_bool(session, "maintenance_mode")
    await SettingsService.set(
        session, "maintenance_mode", "false" if current else "true", db_user.id
    )
    await callback.answer(f"Manutenção: {'OFF' if current else 'ON'}", show_alert=True)
    await cb_cfg_general(callback, session, db_user)


# ========== ADMINS ==========

@router.callback_query(F.data == "admin:cfg_admins")
async def cb_cfg_admins(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    count = (
        await session.execute(select(func.count(User.id)).where(User.is_admin.is_(True)))
    ).scalar_one() or 0
    await callback.message.edit_text(
        f"<b>CONFIGURAR ADMIN</b>\n\nAdministradores: <b>{count}</b>",
        reply_markup=admin_cfg_admins_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:adm_add")
async def cb_adm_add(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.adm_add)
    await callback.message.edit_text("➕ Telegram ID do novo admin:")
    await callback.answer()


@router.message(CfgStates.adm_add)
async def process_adm_add(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ ID inválido.")
        return
    user = await session.get(User, uid)
    if not user:
        await message.answer("❌ Usuário precisa ter usado /start.")
        await state.clear()
        return
    user.is_admin = True
    user.admin_role = "admin"
    session.add(AdminLog(admin_id=db_user.id, action="add_admin", target_id=str(uid)))
    await state.clear()
    await message.answer(f"✅ <code>{uid}</code> é admin.", parse_mode="HTML")


@router.callback_query(F.data == "admin:adm_remove")
async def cb_adm_remove(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.adm_remove)
    await callback.message.edit_text("➖ Telegram ID para remover admin:")
    await callback.answer()


@router.message(CfgStates.adm_remove)
async def process_adm_remove(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ ID inválido.")
        return
    if uid in settings.ADMIN_IDS:
        await message.answer("❌ Não remove o Owner do .env.")
        await state.clear()
        return
    user = await session.get(User, uid)
    if not user:
        await message.answer("❌ Não encontrado.")
        await state.clear()
        return
    user.is_admin = False
    user.admin_role = None
    session.add(AdminLog(admin_id=db_user.id, action="remove_admin", target_id=str(uid)))
    await state.clear()
    await message.answer("✅ Admin removido.")


@router.callback_query(F.data == "admin:adm_list")
async def cb_adm_list(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    result = await session.execute(select(User).where(User.is_admin.is_(True)))
    admins = list(result.scalars().all())
    lines = ["📋 <b>ADMINS</b>\n"]
    for a in admins:
        lines.append(f"• <code>{a.id}</code> @{a.username or 'N/A'}")
    await callback.message.edit_text(
        "\n".join(lines) if admins else "Nenhum admin.",
        reply_markup=admin_cfg_admins_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ========== AFILIADOS ==========

@router.callback_query(F.data == "admin:cfg_affiliate")
async def cb_cfg_aff(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    enabled = await SettingsService.get_bool(session, "affiliate_enabled")
    text = (
        f"<b>AFILIADOS</b>\n\n"
        f"Sistema: <b>{'ON' if enabled else 'OFF'}</b>\n"
        f"Comissão: {await SettingsService.get(session, 'affiliate_commission_percent')}%\n"
        f"Saque mín: R$ {await SettingsService.get(session, 'affiliate_min_withdraw')}\n"
        f"Pontos/recarga: {await SettingsService.get(session, 'points_per_recharge')}\n"
        f"Pontos mín: {await SettingsService.get(session, 'points_min_convert')}\n"
        f"Multiplicador: {await SettingsService.get(session, 'points_multiplier')}"
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
    await SettingsService.set(session, "affiliate_enabled", "false" if cur else "true", db_user.id)
    await cb_cfg_aff(callback, session, db_user)


async def _ask(callback: CallbackQuery, state: FSMContext, st, prompt: str, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(st)
    await callback.message.edit_text(prompt)
    await callback.answer()


@router.callback_query(F.data == "admin:aff_points_recharge")
async def cb_aff_pts(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.aff_points, "⭐ Pontos por recarga:", db_user)


@router.message(CfgStates.aff_points)
async def p_aff_pts(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "points_per_recharge", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_points_min")
async def cb_aff_min(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.aff_min, "📉 Pontos mínimos para converter:", db_user)


@router.message(CfgStates.aff_min)
async def p_aff_min(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "points_min_convert", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_multiplier")
async def cb_aff_mult(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.aff_mult, "✖️ Multiplicador (ex: 0.01):", db_user)


@router.message(CfgStates.aff_mult)
async def p_aff_mult(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "points_multiplier", (message.text or "").replace(",", ".").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_commission")
async def cb_aff_comm(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.aff_commission, "🧲 Comissão %:", db_user)


@router.message(CfgStates.aff_commission)
async def p_aff_comm(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "affiliate_commission_percent", (message.text or "").replace(",", ".").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_min_withdraw")
async def cb_aff_mw(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.aff_min_withdraw, "💸 Saque mínimo R$:", db_user)


@router.message(CfgStates.aff_min_withdraw)
async def p_aff_mw(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "affiliate_min_withdraw", (message.text or "").replace(",", ".").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


# ========== USUÁRIOS ==========

@router.callback_query(F.data == "admin:cfg_users")
async def cb_cfg_users(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    bonus = await SettingsService.get(session, "registration_bonus")
    await callback.message.edit_text(
        f"<b>USUÁRIOS</b>\n\nBônus de registro: <b>R$ {bonus}</b>",
        reply_markup=admin_cfg_users_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:set_reg_bonus")
async def cb_reg_bonus(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.reg_bonus, "🎁 Bônus de registro R$:", db_user)


@router.message(CfgStates.reg_bonus)
async def p_reg_bonus(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "registration_bonus", (message.text or "0").replace(",", ".").strip(), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


# ========== PIX ==========

@router.callback_query(F.data == "admin:cfg_pix")
async def cb_cfg_pix(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    token = await SettingsService.get(session, "mp_access_token") or settings.MP_ACCESS_TOKEN or ""
    show = (token[:18] + "...") if len(token) > 18 else (token or "não definido")
    text = (
        f"<b>CONFIGURAR PIX</b>\n\n"
        f"TOKEN: <code>{show}</code>\n"
        f"MÍN: R$ {await SettingsService.get(session, 'pix_min')}\n"
        f"MÁX: R$ {await SettingsService.get(session, 'pix_max')}\n"
        f"EXPIRAÇÃO: {await SettingsService.get(session, 'pix_expiration_minutes')} min\n"
        f"BÔNUS: {await SettingsService.get(session, 'bonus_percent')}%\n"
        f"MÍN BÔNUS: R$ {await SettingsService.get(session, 'bonus_min_value')}"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_pix_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:pix_token")
async def cb_pix_token(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_token, "🔑 Access Token Mercado Pago:", db_user)


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
    await _ask(callback, state, CfgStates.pix_min, "⬇️ Depósito mínimo:", db_user)


@router.message(CfgStates.pix_min)
async def p_pix_min(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "pix_min", (message.text or "").replace(",", ".").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_max")
async def cb_pix_max(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_max, "⬆️ Depósito máximo:", db_user)


@router.message(CfgStates.pix_max)
async def p_pix_max(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "pix_max", (message.text or "").replace(",", ".").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_exp")
async def cb_pix_exp(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_exp, "⏱ Expiração (minutos):", db_user)


@router.message(CfgStates.pix_exp)
async def p_pix_exp(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "pix_expiration_minutes", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_bonus")
async def cb_pix_bonus(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_bonus, "🎁 Bônus %:", db_user)


@router.message(CfgStates.pix_bonus)
async def p_pix_bonus(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "bonus_percent", (message.text or "").replace(",", ".").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_bonus_min")
async def cb_pix_bonus_min(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_bonus_min, "📌 Mínimo para bônus R$:", db_user)


@router.message(CfgStates.pix_bonus_min)
async def p_pix_bonus_min(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "bonus_min_value", (message.text or "").replace(",", ".").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


# ========== ENTREGA WHATSAPP / BAILEYS ==========

@router.callback_query(F.data == "admin:cfg_delivery")
async def cb_cfg_delivery(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    enabled = await SettingsService.get_bool(session, "baileys_enabled")
    pwd_on = await SettingsService.get_bool(session, "delivery_password_enabled")
    url = await SettingsService.get(session, "baileys_api_url")

    text = (
        f"<b>ENTREGA WHATSAPP (BAILEYS)</b>\n\n"
        f"API Baileys: <b>{'ON 🟢' if enabled else 'OFF 🔴'}</b>\n"
        f"URL: <code>{url or '—'}</code>\n"
        f"Senha de liberação: <b>{'ON 🟢' if pwd_on else 'OFF 🔴'}</b>\n\n"
        f"<b>Fluxo:</b>\n"
        f"1) WhatsApp recebe resumo + imagem (sem login)\n"
        f"2) Cliente confirma no Telegram\n"
        f"3) Se senha ON → digita senha no Telegram\n"
        f"4) Só então o WhatsApp recebe e-mail/senha do produto"
    )

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=f"Baileys ({'ON' if enabled else 'OFF'})",
            callback_data="admin:baileys_toggle",
        )
    )
    b.row(InlineKeyboardButton(text="🔗 URL da API", callback_data="admin:baileys_url"))
    b.row(InlineKeyboardButton(text="🔑 API Key", callback_data="admin:baileys_key"))
    b.row(
        InlineKeyboardButton(
            text=f"Senha liberação ({'ON' if pwd_on else 'OFF'})",
            callback_data="admin:delivery_pwd_toggle",
        )
    )
    b.row(
        InlineKeyboardButton(text="🔐 Definir senha de liberação", callback_data="admin:delivery_pwd_set")
    )
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))

    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:baileys_toggle")
async def cb_bail_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    cur = await SettingsService.get_bool(session, "baileys_enabled")
    await SettingsService.set(session, "baileys_enabled", "false" if cur else "true", db_user.id)
    await cb_cfg_delivery(callback, session, db_user)


@router.callback_query(F.data == "admin:delivery_pwd_toggle")
async def cb_pwd_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    cur = await SettingsService.get_bool(session, "delivery_password_enabled")
    await SettingsService.set(
        session, "delivery_password_enabled", "false" if cur else "true", db_user.id
    )
    await cb_cfg_delivery(callback, session, db_user)


@router.callback_query(F.data == "admin:baileys_url")
async def cb_bail_url(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.baileys_url)
    await callback.message.edit_text(
        "🔗 Envie a URL base da API Baileys\nEx: <code>http://127.0.0.1:3000</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(CfgStates.baileys_url)
async def p_bail_url(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "baileys_api_url", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ URL Baileys salva.")


@router.callback_query(F.data == "admin:baileys_key")
async def cb_bail_key(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.baileys_key)
    await callback.message.edit_text("🔑 Envie a API Key (ou <code>-</code> para limpar):", parse_mode="HTML")
    await callback.answer()


@router.message(CfgStates.baileys_key)
async def p_bail_key(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    val = (message.text or "").strip()
    if val == "-":
        val = ""
    await SettingsService.set(session, "baileys_api_key", val, db_user.id)
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ API Key salva.")


@router.callback_query(F.data == "admin:delivery_pwd_set")
async def cb_pwd_set(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.delivery_pwd)
    await callback.message.edit_text("🔐 Envie a nova senha de liberação da entrega:")
    await callback.answer()


@router.message(CfgStates.delivery_pwd)
async def p_pwd_set(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    pwd = (message.text or "").strip()
    if not pwd:
        await message.answer("❌ Senha vazia.")
        return
    await SettingsService.set(session, "delivery_password", pwd, db_user.id)
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ Senha de liberação atualizada.")


# ========== OUTROS MENUS ==========

@router.callback_query(F.data == "admin:actions")
async def cb_actions(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        return
    await callback.message.edit_text(
        "🛠 <b>AÇÕES</b>", reply_markup=admin_giftcards_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:transactions")
async def cb_transactions(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        return
    await callback.message.edit_text(
        "💳 <b>TRANSAÇÕES</b>", reply_markup=admin_payments_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:updates")
async def cb_updates(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        return
    await callback.message.edit_text(
        "🔄 <b>ATUALIZAÇÕES</b>\n\nVersão: <b>1.0.0</b>",
        reply_markup=admin_back_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:cfg_search")
async def cb_cfg_search(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        return
    await callback.message.edit_text(
        "<b>PESQUISA</b>\n\nPesquisa do cliente já ativa.",
        reply_markup=admin_back_kb("admin:cfg"),
        parse_mode="HTML",
    )
    await callback.answer()
