from datetime import datetime, timezone
from decimal import Decimal

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Order, OrderStatus, Payment, PaymentStatus
from keyboards.admin import admin_main_kb, admin_config_kb, admin_payments_kb

router = Router(name="admin_panel")


def is_admin(user: User) -> bool:
    if user is None:
        return False
    if user.is_admin:
        return True
    admin_ids = getattr(settings, "ADMIN_IDS", []) or []
    return user.id in admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await message.answer("Acesso negado.")
        return

    users_count = (
        await session.execute(select(func.count(User.id)))
    ).scalar_one() or 0

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    revenue_total = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.APPROVED
            )
        )
    ).scalar_one() or 0

    revenue_month = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.APPROVED,
                Payment.created_at >= month_start,
            )
        )
    ).scalar_one() or 0

    revenue_today = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.APPROVED,
                Payment.created_at >= day_start,
            )
        )
    ).scalar_one() or 0

    sales_total = (
        await session.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.DELIVERED)
        )
    ).scalar_one() or 0

    sales_today = (
        await session.execute(
            select(func.count(Order.id)).where(
                Order.status == OrderStatus.DELIVERED,
                Order.created_at >= day_start,
            )
        )
    ).scalar_one() or 0

    text = (
        f"📊 <b>DASHBOARD</b>\n\n"
        f"Software version: <b>V1.0.0</b>\n\n"
        f"<b>Métricas do business</b>\n"
        f"Users: <b>{users_count}</b>\n"
        f"Receita total: <b>R$ {float(revenue_total):.2f}</b>\n"
        f"Receita mensal: <b>R$ {float(revenue_month):.2f}</b>\n"
        f"Receita de hoje: <b>R$ {float(revenue_today):.2f}</b>\n"
        f"Vendas total: <b>{sales_total}</b>\n"
        f"Vendas hoje: <b>{sales_today}</b>\n\n"
        f"Use os botões abaixo para configurar"
    )
    await message.answer(text, reply_markup=admin_main_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin:main")
async def cb_admin_main(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    await callback.message.edit_text(
        "👑 <b>PAINEL ADMIN</b>\n\nEscolha uma opção:",
        reply_markup=admin_main_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:dashboard")
async def cb_dashboard(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    # reusa a mesma lógica do /admin via mensagem editada
    users_count = (
        await session.execute(select(func.count(User.id)))
    ).scalar_one() or 0
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_total = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.APPROVED
            )
        )
    ).scalar_one() or 0
    revenue_month = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.APPROVED,
                Payment.created_at >= month_start,
            )
        )
    ).scalar_one() or 0
    revenue_today = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.APPROVED,
                Payment.created_at >= day_start,
            )
        )
    ).scalar_one() or 0
    sales_total = (
        await session.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.DELIVERED)
        )
    ).scalar_one() or 0
    sales_today = (
        await session.execute(
            select(func.count(Order.id)).where(
                Order.status == OrderStatus.DELIVERED,
                Order.created_at >= day_start,
            )
        )
    ).scalar_one() or 0
    text = (
        f"📊 <b>DASHBOARD</b>\n\n"
        f"Users: <b>{users_count}</b>\n"
        f"Receita total: <b>R$ {float(revenue_total):.2f}</b>\n"
        f"Receita mensal: <b>R$ {float(revenue_month):.2f}</b>\n"
        f"Receita de hoje: <b>R$ {float(revenue_today):.2f}</b>\n"
        f"Vendas total: <b>{sales_total}</b>\n"
        f"Vendas hoje: <b>{sales_today}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_main_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:cfg")
async def cb_cfg(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    await callback.message.edit_text(
        "⚙️ <b>MENU DE CONFIGURAÇÕES DO BOT</b>\n\n"
        f"Admin: <b>Sim</b>\n"
        f"ID: <code>{db_user.id}</code>",
        reply_markup=admin_config_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:transactions")
async def cb_transactions(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        return
    await callback.message.edit_text(
        "💳 <b>TRANSAÇÕES</b>",
        reply_markup=admin_payments_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:actions")
async def cb_actions(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        return
    from keyboards.admin import admin_giftcards_kb

    await callback.message.edit_text(
        "🛠 <b>AÇÕES</b>\n\nGift cards e utilidades:",
        reply_markup=admin_giftcards_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:updates")
async def cb_updates(callback: CallbackQuery, db_user: User):
    if not is_admin(db_user):
        return
    from keyboards.admin import admin_back_kb

    await callback.message.edit_text(
        "🔄 <b>ATUALIZAÇÕES</b>\n\nVersão atual: <b>1.0.0</b>",
        reply_markup=admin_back_kb("admin:main"),
        parse_mode="HTML",
    )
    await callback.answer()
