from decimal import Decimal

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Order, OrderStatus, TransactionType
from handlers.admin.panel import is_admin
from keyboards.admin import admin_user_actions_kb, admin_cfg_users_kb
from services.balance import BalanceService

router = Router(name="admin_users")


class UserAdminStates(StatesGroup):
    add_balance = State()
    remove_balance = State()


@router.callback_query(F.data.startswith("admin:user_add_balance:"))
async def cb_add_balance(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    uid = int(callback.data.split(":")[2])
    await state.set_state(UserAdminStates.add_balance)
    await state.update_data(target_id=uid)
    await callback.message.edit_text(f"💰 Valor para adicionar ao usuário <code>{uid}</code>:", parse_mode="HTML")
    await callback.answer()


@router.message(UserAdminStates.add_balance)
async def process_add_balance(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    data = await state.get_data()
    await state.clear()
    try:
        amount = Decimal((message.text or "").replace(",", ".").strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        await message.answer("❌ Valor inválido.")
        return
    target_id = data["target_id"]
    user = await BalanceService.add_balance(
        session,
        target_id,
        amount,
        TransactionType.ADMIN_ADD,
        description=f"Admin {db_user.id} adicionou saldo",
        admin_id=db_user.id,
    )
    await message.answer(
        f"✅ +R$ {amount:.2f} para <code>{target_id}</code>\n"
        f"Saldo atual: <b>R$ {user.balance:.2f}</b>",
        parse_mode="HTML",
        reply_markup=admin_user_actions_kb(target_id),
    )


@router.callback_query(F.data.startswith("admin:user_remove_balance:"))
async def cb_remove_balance(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    uid = int(callback.data.split(":")[2])
    await state.set_state(UserAdminStates.remove_balance)
    await state.update_data(target_id=uid)
    await callback.message.edit_text(f"💸 Valor para remover do usuário <code>{uid}</code>:", parse_mode="HTML")
    await callback.answer()


@router.message(UserAdminStates.remove_balance)
async def process_remove_balance(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    data = await state.get_data()
    await state.clear()
    try:
        amount = Decimal((message.text or "").replace(",", ".").strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        await message.answer("❌ Valor inválido.")
        return
    target_id = data["target_id"]
    try:
        user = await BalanceService.remove_balance(
            session,
            target_id,
            amount,
            TransactionType.ADMIN_REMOVE,
            description=f"Admin {db_user.id} removeu saldo",
            admin_id=db_user.id,
        )
    except ValueError as e:
        await message.answer(f"❌ {e}")
        return
    await message.answer(
        f"✅ -R$ {amount:.2f} de <code>{target_id}</code>\n"
        f"Saldo atual: <b>R$ {user.balance:.2f}</b>",
        parse_mode="HTML",
        reply_markup=admin_user_actions_kb(target_id),
    )


@router.callback_query(F.data.startswith("admin:user_block:"))
async def cb_block(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    uid = int(callback.data.split(":")[2])
    user = await session.get(User, uid)
    if not user:
        await callback.answer("Usuário não encontrado.", show_alert=True)
        return
    user.is_blocked = not user.is_blocked
    status = "bloqueado" if user.is_blocked else "desbloqueado"
    await callback.message.edit_text(
        f"👤 Usuário <code>{uid}</code> {status}.",
        parse_mode="HTML",
        reply_markup=admin_user_actions_kb(uid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user_history:"))
async def cb_user_history(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    uid = int(callback.data.split(":")[2])
    result = await session.execute(
        select(Order)
        .where(Order.user_id == uid, Order.status == OrderStatus.DELIVERED)
        .order_by(Order.created_at.desc())
        .limit(15)
    )
    orders = list(result.scalars().all())
    if not orders:
        text = f"📊 Sem compras para <code>{uid}</code>."
    else:
        lines = [f"📊 <b>Histórico</b> <code>{uid}</code>\n"]
        for o in orders:
            lines.append(
                f"• {o.created_at.strftime('%d/%m/%Y')} | R$ {o.total_price:.2f} | {o.uuid[:8]}…"
            )
        text = "\n".join(lines)
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=admin_user_actions_kb(uid)
    )
    await callback.answer()
