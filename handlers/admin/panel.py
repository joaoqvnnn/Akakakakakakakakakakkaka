from decimal import Decimal
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Order, OrderStatus
from keyboards.admin import admin_main_kb
from services.settings_service import SettingsService

router = Router(name="admin_panel")


def is_admin(db_user: User | None) -> bool:
    if not db_user:
        return False
    if db_user.is_admin:
        return True
    return db_user.id in settings.ADMIN_IDS


async def dashboard_text(session: AsyncSession) -> str:
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)

    users = (await session.execute(select(func.count(User.id)))).scalar_one() or 0

    sales_total = (
        await session.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.DELIVERED)
        )
    ).scalar_one() or 0

    sales_today = (
        await session.execute(
            select(func.count(Order.id)).where(
                Order.status == OrderStatus.DELIVERED,
                Order.created_at >= today,
            )
        )
    ).scalar_one() or 0

    rev_total = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total_price), 0)).where(
                Order.status == OrderStatus.DELIVERED
            )
        )
    ).scalar_one() or Decimal("0")

    rev_today = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total_price), 0)).where(
                Order.status == OrderStatus.DELIVERED,
                Order.created_at >= today,
            )
        )
    ).scalar_one() or Decimal("0")

    rev_month = (
        await session.execute(
            select(func.coalesce(func.sum(Order.total_price), 0)).where(
                Order.status == OrderStatus.DELIVERED,
                Order.created_at >= month_start,
            )
        )
    ).scalar_one() or Decimal("0")

    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)

    return (
        f"📊 <b>DASHBOARD — {store}</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"💰 Receita total: <b>R$ {rev_total:.2f}</b>\n"
        f"📅 Receita mensal: <b>R$ {rev_month:.2f}</b>\n"
        f"💵 Receita de hoje: <b>R$ {rev_today:.2f}</b>\n"
        f"🛒 Vendas total: <b>{sales_total}</b>\n"
        f"🛒 Vendas hoje: <b>{sales_today}</b>\n\n"
        f"Use os botões abaixo para configurar:"
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await message.answer("🚫 Acesso negado.")
        return
    await SettingsService.ensure_defaults(session)
    text = await dashboard_text(session)
    await message.answer(text, reply_markup=admin_main_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin:main")
@router.callback_query(F.data == "admin:dashboard")
async def cb_admin_main(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    text = await dashboard_text(session)
    await callback.message.edit_text(
        text, reply_markup=admin_main_kb(), parse_mode="HTML"
    )
    await callback.answer()
