from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Product, ProductStatus
from keyboards.client_dynamic import alerts_list_kb
from services.alerts import AlertService

router = Router(name="alerts")


@router.callback_query(F.data == "alerts")
async def cb_alerts(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    result = await session.execute(
        select(Product)
        .where(Product.status == ProductStatus.ACTIVE)
        .order_by(Product.name)
        .limit(40)
    )
    products = list(result.scalars().all())
    active_map = await AlertService.list_active_map(session, db_user.id)

    text = (
        "⚠️ <b>Sistema de alertas</b>\n\n"
        "Seja notificado quando seu serviço favorito for abastecido 🤩\n\n"
        "🎯 Selecione abaixo os serviços. ✅ = alerta ativo.\n\n"
        "Lista de serviços:"
    )
    kb = await alerts_list_kb(session, products, active_map)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("alert_toggle:"))
async def cb_toggle(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    product_id = int(callback.data.split(":")[1])
    active = await AlertService.toggle_alert(session, db_user.id, product_id)
    await callback.answer(
        "Alerta ativado ✅" if active else "Alerta desativado ❌",
        show_alert=False,
    )

    result = await session.execute(
        select(Product)
        .where(Product.status == ProductStatus.ACTIVE)
        .order_by(Product.name)
        .limit(40)
    )
    products = list(result.scalars().all())
    active_map = await AlertService.list_active_map(session, db_user.id)
    kb = await alerts_list_kb(session, products, active_map)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        await cb_alerts(callback, session, db_user)
