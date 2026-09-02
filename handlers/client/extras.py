from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from config import settings
from database.models import User, Product, Order, OrderStatus, Payment, PaymentStatus
from keyboards.client import ranking_kb, support_kb, back_kb
from services.settings_service import SettingsService

router = Router(name="extras")


@router.callback_query(F.data == "ranking")
@router.callback_query(F.data.startswith("ranking:"))
async def cb_ranking(callback: CallbackQuery, session: AsyncSession, db_user: User):
    tab = "products"
    if callback.data.startswith("ranking:"):
        tab = callback.data.split(":")[1]

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if tab == "products":
        result = await session.execute(
            select(Product.name, Product.sold_count)
            .where(Product.sold_count > 0)
            .order_by(Product.sold_count.desc())
            .limit(10)
        )
        rows = result.all()
        lines = ["🏆 <b>Ranking dos serviços mais vendidos</b>\n"]
        medals = ["🥇", "🥈", "🥉"]
        for i, (name, sold) in enumerate(rows, 1):
            medal = medals[i - 1] if i <= 3 else ""
            lines.append(f"{i}°) {name} {medal} — <b>{sold}</b> pedidos")
        if not rows:
            lines.append("Ainda não há vendas registradas.")
        text = "\n".join(lines)

    elif tab == "recharges":
        result = await session.execute(
            select(User.first_name, User.username, User.id, User.total_deposited)
            .where(User.total_deposited > 0)
            .order_by(User.total_deposited.desc())
            .limit(10)
        )
        rows = result.all()
        lines = ["🏆 <b>Ranking quem mais recarregou</b>\n"]
        medals = ["🥇", "🥈", "🥉"]
        for i, (first, uname, uid, total) in enumerate(rows, 1):
            label = first or (f"@{uname}" if uname else f"ID: {uid}")
            medal = medals[i - 1] if i <= 3 else ""
            lines.append(f"{i}°) {label} {medal}")
        if not rows:
            lines.append("Ainda sem recargas.")
        # Dica para o usuário atual
        top_min = rows[-1][3] if len(rows) >= 10 else None
        if top_min is not None and db_user.total_deposited < top_min:
            faltam = top_min - db_user.total_deposited
            lines.append(
                f"\n💡 Faltam cerca de <b>R$ {faltam:.2f}</b> para entrar no top 10."
            )
        text = "\n".join(lines)

    elif tab == "balance":
        result = await session.execute(
            select(User.first_name, User.username, User.id, User.balance)
            .where(User.balance > 0)
            .order_by(User.balance.desc())
            .limit(10)
        )
        rows = result.all()
        lines = ["🏆 <b>Ranking usuários com mais saldo</b>\n"]
        medals = ["🥇", "🥈", "🥉"]
        for i, (first, uname, uid, bal) in enumerate(rows, 1):
            label = first or (f"@{uname}" if uname else f"ID: {uid}")
            medal = medals[i - 1] if i <= 3 else ""
            lines.append(f"{i}°) {label} {medal}")
        if not rows:
            lines.append("Nenhum saldo positivo no ranking.")
        text = "\n".join(lines)

    else:  # purchases
        result = await session.execute(
            select(
                User.first_name,
                User.username,
                User.id,
                func.count(Order.id).label("cnt"),
            )
            .join(Order, Order.user_id == User.id)
            .where(Order.status == OrderStatus.DELIVERED)
            .group_by(User.id)
            .order_by(func.count(Order.id).desc())
            .limit(10)
        )
        rows = result.all()
        lines = ["🏆 <b>Ranking quem mais comprou</b>\n"]
        medals = ["🥇", "🥈", "🥉"]
        for i, (first, uname, uid, cnt) in enumerate(rows, 1):
            label = first or (f"@{uname}" if uname else f"ID: {uid}")
            medal = medals[i - 1] if i <= 3 else ""
            lines.append(f"{i}°) {label} {medal} — {cnt} compras")
        if not rows:
            lines.append("Ainda sem compras.")
        text = "\n".join(lines)

    await callback.message.edit_text(
        text, reply_markup=ranking_kb(tab), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, session: AsyncSession):
    link = await SettingsService.get(
        session, "support_link", settings.SUPPORT_LINK or settings.SUPPORT_USERNAME
    )
    text = (
        "🎧 <b>Atendimento</b>\n\n"
        "Precisa de ajuda? Fale com nosso suporte."
    )
    await callback.message.edit_text(
        text, reply_markup=support_kb(link), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery, session: AsyncSession):
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    text = (
        f"ℹ️ <b>Sobre o Bot</b>\n\n"
        f"🏪 Nome: <b>{store}</b>\n"
        f"🤖 Bot: @{settings.BOT_USERNAME}\n"
        f"🛡 Entrega 100% automática\n"
        f"💳 PIX instantâneo\n\n"
        f"Use /termos para ver os termos de uso."
    )
    await callback.message.edit_text(
        text, reply_markup=back_kb("main_menu"), parse_mode="HTML"
    )
    await callback.answer()
