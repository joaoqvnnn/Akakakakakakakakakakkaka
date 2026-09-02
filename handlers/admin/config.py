from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
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


# ---------- GERAIS ----------

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
        "O separador divide dados em massa.\n"
        f"Ex: <code>NOME{sep}VALOR</code>\n\n"
        "Use os botões abaixo:"
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
    await callback.message.edit_text(
        "🔗 Envie o link de suporte (https://t.me/... ou https://wa.me/55...):"
    )
    await callback.answer()


@router.message(CfgStates.support)
async def process_support(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    link = (message.text or "").strip()
    await SettingsService.set(session, "support_link", link, db_user.id)
    await state.clear()
    await message.answer(f"✅ Suporte atualizado:\n{link}")


@router.callback_query(F.data == "admin:set_separator")
async def cb_set_sep(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.separator)
    await callback.message.edit_text("📌 Envie o novo separador (ex: === ):")
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
    await callback.message.edit_text("📨 Envie o ID do chat/canal de logs (ex: -100123...):")
    await callback.answer()


@router.message(CfgStates.logs_chat)
async def process_logs(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    chat_id = (message.text or "").strip()
    await SettingsService.set(session, "logs_chat_id", chat_id, db_user.id)
    await state.clear()
    await message.answer(f"✅ Logs: <code>{chat_id}</code>", parse_mode="HTML")


@router.callback_query(F.data == "admin:toggle_maintenance")
async def cb_toggle_maint(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    current = await SettingsService.get_bool(session, "maintenance_mode")
    new_val = "false" if current else "true"
    await SettingsService.set(session, "maintenance_mode", new_val, db_user.id)
    await callback.answer(
        f"Manutenção: {'ON' if new_val == 'true' else 'OFF'}", show_alert=True
    )
    await cb_cfg_general(callback, session, db_user)


# ---------- ADMINS ----------

@router.callback_query(F.data == "admin:cfg_admins")
async def cb_cfg_admins(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    count = (
        await session.execute(select(func.count(User.id)).where(User.is_admin.is_(True)))
    ).scalar_one() or 0
    text = (
        f"<b>PAINEL CONFIGURAR ADMIN</b>\n\n"
        f"Administradores: <b>{count}</b>\n\n"
        "Use os botões abaixo:"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_admins_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:adm_add")
async def cb_adm_add(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.adm_add)
    await callback.message.edit_text("➕ Envie o Telegram ID do novo admin:")
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
        await message.answer("❌ Usuário precisa ter usado /start antes.")
        await state.clear()
        return
    user.is_admin = True
    user.admin_role = "admin"
    session.add(AdminLog(admin_id=db_user.id, action="add_admin", target_type="user", target_id=str(uid)))
    await state.clear()
    await message.answer(f"✅ <code>{uid}</code> agora é admin.", parse_mode="HTML")


@router.callback_query(F.data == "admin:adm_remove")
async def cb_adm_remove(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CfgStates.adm_remove)
    await callback.message.edit_text("➖ Envie o Telegram ID do admin a remover:")
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
        await message.answer("❌ Não é possível remover o Owner do .env.")
        await state.clear()
        return
    user = await session.get(User, uid)
    if not user:
        await message.answer("❌ Usuário não encontrado.")
        await state.clear()
        return
    user.is_admin = False
    user.admin_role = None
    session.add(AdminLog(admin_id=db_user.id, action="remove_admin", target_type="user", target_id=str(uid)))
    await state.clear()
    await message.answer(f"✅ Admin <code>{uid}</code> removido.", parse_mode="HTML")


@router.callback_query(F.data == "admin:adm_list")
async def cb_adm_list(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    result = await session.execute(select(User).where(User.is_admin.is_(True)))
    admins = list(result.scalars().all())
    if not admins:
        text = "Nenhum admin no banco."
    else:
        lines = ["📋 <b>LISTA DE ADMINS</b>\n"]
        for a in admins:
            lines.append(f"• <code>{a.id}</code> — @{a.username or 'N/A'}")
        text = "\n".join(lines)
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_admins_kb(), parse_mode="HTML"
    )
    await callback.answer()


# ---------- AFILIADOS ----------

@router.callback_query(F.data == "admin:cfg_affiliate")
async def cb_cfg_aff(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    enabled = await SettingsService.get_bool(session, "affiliate_enabled")
    points = await SettingsService.get(session, "points_per_recharge")
    min_c = await SettingsService.get(session, "points_min_convert")
    mult = await SettingsService.get(session, "points_multiplier")
    commission = await SettingsService.get(session, "affiliate_commission_percent")
    min_w = await SettingsService.get(session, "affiliate_min_withdraw")
    text = (
        f"<b>CONFIGURAR AFILIADOS</b>\n\n"
        f"Sistema: <b>{'ON 🟢' if enabled else 'OFF 🔴'}</b>\n"
        f"Comissão: <b>{commission}%</b>\n"
        f"Saque mínimo: <b>R$ {min_w}</b>\n"
        f"Pontos por recarga: <b>{points}</b>\n"
        f"Pontos mín. converter: <b>{min_c}</b>\n"
        f"Multiplicador: <b>{mult}</b>\n\n"
        f"Ex: 500 pontos × 0.01 = R$ 5,00"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_affiliate_kb(enabled), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:aff_toggle")
async def cb_aff_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    current = await SettingsService.get_bool(session, "affiliate_enabled")
    await SettingsService.set(
        session, "affiliate_enabled", "false" if current else "true", db_user.id
    )
    await callback.answer("Atualizado!")
    await cb_cfg_aff(callback, session, db_user)


async def _ask(callback, state, new_state, prompt: str, db_user):
    if not is_admin(db_user):
        return
    await state.set_state(new_state)
    await callback.message.edit_text(prompt)
    await callback.answer()


@router.callback_query(F.data == "admin:aff_points_recharge")
async def cb_aff_points(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.aff_points, "⭐ Pontos por recarga do indicado:", db_user)


@router.message(CfgStates.aff_points)
async def p_aff_points(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "points_per_recharge", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_points_min")
async def cb_aff_min(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.aff_min, "📉 Mínimo de pontos para converter:", db_user)


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
        session, "points_multiplier", (message.text or "").strip().replace(",", "."), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_commission")
async def cb_aff_comm(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.aff_commission, "🧲 Comissão % (ex: 20):", db_user)


@router.message(CfgStates.aff_commission)
async def p_aff_comm(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "affiliate_commission_percent", (message.text or "").strip().replace(",", "."), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:aff_min_withdraw")
async def cb_aff_mw(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.aff_min_withdraw, "💸 Saque mínimo R$ (ex: 20):", db_user)


@router.message(CfgStates.aff_min_withdraw)
async def p_aff_mw(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "affiliate_min_withdraw", (message.text or "").strip().replace(",", "."), db_user.id
    )
    await state.clear()
    await message.answer("✅ Salvo.")


# ---------- USUÁRIOS ----------

@router.callback_query(F.data == "admin:cfg_users")
async def cb_cfg_users(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    bonus = await SettingsService.get(session, "registration_bonus")
    text = (
        f"<b>CONFIGURAR USUÁRIOS</b>\n\n"
        f"Bônus de registro: <b>R$ {bonus}</b>\n\n"
        "Use os botões abaixo:"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_users_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:set_reg_bonus")
async def cb_reg_bonus(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.reg_bonus, "🎁 Bônus de registro (ex: 0 ou 1.50):", db_user)


@router.message(CfgStates.reg_bonus)
async def p_reg_bonus(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(
        session, "registration_bonus", (message.text or "0").strip().replace(",", "."), db_user.id
    )
    await state.clear()
    await message.answer("✅ Bônus de registro salvo.")


# ---------- PIX ----------

@router.callback_query(F.data == "admin:cfg_pix")
async def cb_cfg_pix(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    token = await SettingsService.get(session, "mp_access_token") or settings.MP_ACCESS_TOKEN or ""
    token_show = (token[:18] + "...") if len(token) > 18 else (token or "não definido")
    pix_min = await SettingsService.get(session, "pix_min")
    pix_max = await SettingsService.get(session, "pix_max")
    exp = await SettingsService.get(session, "pix_expiration_minutes")
    bonus = await SettingsService.get(session, "bonus_percent")
    bonus_min = await SettingsService.get(session, "bonus_min_value")
    text = (
        f"<b>CONFIGURAR PIX</b>\n\n"
        f"TOKEN MP: <code>{token_show}</code>\n"
        f"DEPÓSITO MÍN: <b>R$ {pix_min}</b>\n"
        f"DEPÓSITO MÁX: <b>R$ {pix_max}</b>\n"
        f"EXPIRAÇÃO: <b>{exp} min</b>\n"
        f"BÔNUS: <b>{bonus}%</b>\n"
        f"MÍN PARA BÔNUS: <b>R$ {bonus_min}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_cfg_pix_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:pix_token")
async def cb_pix_token(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_token, "🔑 Envie o Access Token do Mercado Pago:", db_user)


@router.message(CfgStates.pix_token)
async def p_pix_token(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    token = (message.text or "").strip()
    await SettingsService.set(session, "mp_access_token", token, db_user.id)
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ Token Mercado Pago atualizado.")


@router.callback_query(F.data == "admin:pix_min")
async def cb_pix_min(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_min, "⬇️ Depósito mínimo (ex: 4.00):", db_user)


@router.message(CfgStates.pix_min)
async def p_pix_min(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "pix_min", (message.text or "").strip().replace(",", "."), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_max")
async def cb_pix_max(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_max, "⬆️ Depósito máximo:", db_user)


@router.message(CfgStates.pix_max)
async def p_pix_max(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "pix_max", (message.text or "").strip().replace(",", "."), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_exp")
async def cb_pix_exp(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_exp, "⏱ Expiração em minutos (ex: 10):", db_user)


@router.message(CfgStates.pix_exp)
async def p_pix_exp(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "pix_expiration_minutes", (message.text or "").strip(), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_bonus")
async def cb_pix_bonus(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_bonus, "🎁 Bônus % (ex: 10):", db_user)


@router.message(CfgStates.pix_bonus)
async def p_pix_bonus(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "bonus_percent", (message.text or "").strip().replace(",", "."), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


@router.callback_query(F.data == "admin:pix_bonus_min")
async def cb_pix_bonus_min(callback: CallbackQuery, state: FSMContext, db_user: User):
    await _ask(callback, state, CfgStates.pix_bonus_min, "📌 Valor mínimo para ganhar bônus:", db_user)


@router.message(CfgStates.pix_bonus_min)
async def p_pix_bonus_min(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    await SettingsService.set(session, "bonus_min_value", (message.text or "").strip().replace(",", "."), db_user.id)
    await state.clear()
    await message.answer("✅ Salvo.")


# ---------- MENUS AÇÕES / TRANSAÇÕES / UPDATES ----------

@router.callback_query(F.data == "admin:actions")
async def cb_actions(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        return
    await callback.message.edit_text(
        "🛠 <b>AÇÕES</b>\n\nGift Cards e ações rápidas:",
        reply_markup=admin_giftcards_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:transactions")
async def cb_transactions(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        return
    await callback.message.edit_text(
        "💳 <b>TRANSAÇÕES</b>\n\nFiltre os pagamentos:",
        reply_markup=admin_payments_kb(),
        parse_mode="HTML",
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
        "<b>PESQUISA DE SERVIÇOS</b>\n\nPesquisa do cliente já ativa.\nImagens por serviço: em breve.",
        reply_markup=admin_back_kb("admin:cfg"),
        parse_mode="HTML",
    )
    await callback.answer()
