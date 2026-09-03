from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from config import settings
from database.models import User, Product, Order, OrderStatus, Payment, PaymentStatus
from keyboards.client_dynamic import ranking_kb, support_kb, back_kb
from services.settings_service import SettingsService

router = Router(name="extras")


@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, session: AsyncSession):
    link = await SettingsService.get(session, "support_link", settings.SUPPORT_LINK)
    kb = await support_kb(session, link)
    await callback.message.edit_text(
        "🎧 <b>Atendimento</b>\n\nFale com nosso suporte:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery, session: AsyncSession):
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    text = (
        f"ℹ️ <b>Sobre o Bot</b>\n\n"
        f"Loja: <b>{store}</b>\n"
        f"Versão: <b>1.0.0</b>\n"
        f"Entrega automática 24h\n"
        f"Pagamentos via PIX"
    )
    kb = await back_kb(session, "main_menu")
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.in_({"ranking", "ranking:products"}))
async def cb_ranking_products(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(Product.name, func.count(Order.id).label("cnt"))
        .join(Order, Order.product_id == Product.id)
        .where(
            Order.status == OrderStatus.DELIVERED,
            Order.created_at >= month_start,
        )
        .group_by(Product.id, Product.name)
        .order_by(func.count(Order.id).desc())
        .limit(10)
    )
    rows = result.all()
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Ranking dos serviços mais vendidos (deste mês)</b>\n"]
    if not rows:
        lines.append("Ainda sem vendas este mês.")
    else:
        for i, (name, cnt) in enumerate(rows, 1):
            m = medals[i - 1] if i <= 3 else ""
            lines.append(f"{i}°) {name} {m} — Com {cnt} pedidos")
    kb = await ranking_kb(session, "products")
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "ranking:recharges")
async def cb_ranking_recharges(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(
            User.id,
            User.first_name,
            User.username,
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
        )
        .join(Payment, Payment.user_id == User.id)
        .where(
            Payment.status == PaymentStatus.APPROVED,
            Payment.created_at >= month_start,
        )
        .group_by(User.id)
        .order_by(func.sum(Payment.amount).desc())
        .limit(10)
    )
    rows = result.all()
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Ranking quem mais recarregou (deste mês)</b>\n"]
    for i, (uid, first, username, total) in enumerate(rows, 1):
        m = medals[i - 1] if i <= 3 else ""
        name = first or (f"@{username}" if username else f"ID: {uid}")
        lines.append(f"{i}°) {name} {m}")
    if not any(r[0] == db_user.id for r in rows):
        lines.append("\n💡 Você ainda não está no ranking.")
    kb = await ranking_kb(session, "recharges")
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "ranking:balance")
async def cb_ranking_balance(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    result = await session.execute(select(User).order_by(User.balance.desc()).limit(10))
    users = list(result.scalars().all())
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Ranking usuários com mais saldo</b>\n"]
    for i, u in enumerate(users, 1):
        m = medals[i - 1] if i <= 3 else ""
        name = u.first_name or (f"@{u.username}" if u.username else f"ID: {u.id}")
        lines.append(f"{i}°) {name} {m}")
    if db_user.id not in [u.id for u in users]:
        lines.append("\n💡 Você ainda não está no ranking.")
    kb = await ranking_kb(session, "balance")
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "ranking:purchases")
async def cb_ranking_purchases(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(
            User.id,
            User.first_name,
            User.username,
            func.count(Order.id).label("cnt"),
        )
        .join(Order, Order.user_id == User.id)
        .where(
            Order.status == OrderStatus.DELIVERED,
            Order.created_at >= month_start,
        )
        .group_by(User.id)
        .order_by(func.count(Order.id).desc())
        .limit(10)
    )
    rows = result.all()
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Ranking quem mais comprou (deste mês)</b>\n"]
    for i, (uid, first, username, cnt) in enumerate(rows, 1):
        m = medals[i - 1] if i <= 3 else ""
        name = first or (f"@{username}" if username else f"ID: {uid}")
        lines.append(f"{i}°) {name} {m}")
    if not any(r[0] == db_user.id for r in rows):
        lines.append("\n💡 Você ainda não está no ranking.")
    kb = await ranking_kb(session, "purchases")
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()
