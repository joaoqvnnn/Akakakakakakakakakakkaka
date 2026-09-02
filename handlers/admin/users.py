from decimal import Decimal

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserStatus, AdminLog, TransactionType
from keyboards.admin import admin_user_actions_kb, admin_cfg_users_kb, admin_back_kb
from handlers.admin.panel import is_admin
from services.balance import BalanceService

router = Router(name="admin_users")


class UserStates(StatesGroup):
    search = State()
    add_balance = State()
    remove_balance = State()


@router.callback_query(F.data == "admin:user_search")
async def cb_user_search(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(UserStates.search)
    await callback.message.edit_text(
        "🔎 Envie o Telegram ID ou @username do usuário:"
    )
    await callback.answer()


@router.message(UserStates.search)
async def process_search(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    raw = (message.text or "").strip().lstrip("@")
    await state.clear()
    user = None
    if raw.isdigit():
        user = await session.get(User, int(raw))
    else:
        result = await session.execute(select(User).where(User.username == raw))
        user = result.scalar_one_or_none()
    if not user:
        await message.answer("❌ Usuário não encontrado.")
        return
    text = (
        f"👤 <b>USUÁRIO</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Username: @{user.username or 'N/A'}\n"
        f"Nome: {user.first_name or '—'}\n"
        f"💰 Saldo: <b>R$ {user.balance:.2f}</b>\n"
        f"💠 Depositado: R$ {user.total_deposited:.2f}\n"
        f"🛒 Gasto: R$ {user.total_spent:.2f}\n"
        f"🤝 Indicações: {user.total_referrals}\n"
        f"🪙 Comissão: R$ {user.affiliate_balance:.2f}\n"
        f"Status: {user.status.value}"
    )
    await message.answer(
        text, reply_markup=admin_user_actions_kb(user.id), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin:user_add_balance:"))
async def cb_add_bal(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    uid = int(callback.data.split(":")[2])
    await state.set_state(UserStates.add_balance)
    await state.update_data(target_id=uid)
    await callback.message.edit_text("💰 Envie o valor a adicionar:")
    await callback.answer()


@router.message(UserStates.add_balance)
async def process_add_bal(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    data = await state.get_data()
    await state.clear()
    try:
        amount = Decimal((message.text or "").replace(",", "."))
    except Exception:
        await message.answer("❌ Valor inválido.")
        return
    uid = data["target_id"]
    await BalanceService.add_balance(
        session, uid, amount, TransactionType.ADMIN_ADD,
        description=f"Admin {db_user.id}", admin_id=db_user.id
    )
    session.add(AdminLog(admin_id=db_user.id, action="add_balance", target_type="user", target_id=str(uid), details={"amount": str(amount)}))
    await message.answer(f"✅ R$ {amount:.2f} creditado em {uid}.")


@router.callback_query(F.data.startswith("admin:user_remove_balance:"))
async def cb_rm_bal(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    uid = int(callback.data.split(":")[2])
    await state.set_state(UserStates.remove_balance)
    await state.update_data(target_id=uid)
    await callback.message.edit_text("💸 Envie o valor a remover:")
    await callback.answer()


@router.message(UserStates.remove_balance)
async def process_rm_bal(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    data = await state.get_data()
    await state.clear()
    try:
        amount = Decimal((message.text or "").replace(",", "."))
    except Exception:
        await message.answer("❌ Valor inválido.")
        return
    uid = data["target_id"]
    try:
        await BalanceService.remove_balance(
            session, uid, amount, TransactionType.ADMIN_REMOVE,
            description=f"Admin {db_user.id}", admin_id=db_user.id
        )
    except ValueError as e:
        await message.answer(f"❌ {e}")
        return
    session.add(AdminLog(admin_id=db_user.id, action="remove_balance", target_type="user", target_id=str(uid), details={"amount": str(amount)}))
    await message.answer(f"✅ R$ {amount:.2f} removido de {uid}.")


@router.callback_query(F.data.startswith("admin:user_block:"))
async def cb_block(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    uid = int(callback.data.split(":")[2])
    user = await session.get(User, uid)
    if not user:
        await callback.answer("Não encontrado.", show_alert=True)
        return
    if user.status == UserStatus.BLOCKED:
        user.status = UserStatus.ACTIVE
        await callback.answer("Desbloqueado.")
    else:
        user.status = UserStatus.BLOCKED
        await callback.answer("Bloqueado.")
    session.add(AdminLog(admin_id=db_user.id, action="toggle_block", target_id=str(uid)))
    await callback.message.edit_text(
        f"👤 {uid} — status: <b>{user.status.value}</b>",
        reply_markup=admin_user_actions_kb(uid),
        parse_mode="HTML",
    )
