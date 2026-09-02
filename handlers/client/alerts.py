from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Product, ProductStatus
from keyboards.client import alerts_list_kb
from services.alerts import AlertService

router = Router(name="alerts")


@router.callback_query(F.data == "alerts")
async def cb_alerts(callback: CallbackQuery, session: AsyncSession, db_user: User):
    result = await session.execute(
        select(Product)
        .where(Product.status == ProductStatus.ACTIVE)
        .order_by(Product.name)
        .limit(40)
    )
    products = list(result.scalars().all())

    user_alerts = await AlertService.get_user_alerts(session, db_user.id)
    active_map = {a.product_id: a.is_active for a in user_alerts}

    text = (
        "⚠️ <b>Sistema de Alertas</b>\n\n"
        "Seja notificado quando seu serviço favorito for abastecido 🤩\n\n"
        "🎯 Selecione abaixo os serviços. "
        "✅ = ativo | ❌ = desativado\n"
    )
    if not products:
        text += "\nNenhum produto disponível."

    await callback.message.edit_text(
        text,
        reply_markup=alerts_list_kb(products, active_map),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("alert_toggle:"))
async def cb_alert_toggle(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    product_id = int(callback.data.split(":")[1])
    product = await session.get(Product, product_id)
    if not product:
        await callback.answer("Produto não encontrado.", show_alert=True)
        return

    is_active = await AlertService.toggle_alert(session, db_user.id, product_id)
    if is_active:
        await callback.answer(f"✅ Alerta ativado: {product.name}")
    else:
        await callback.answer(f"❌ Alerta desativado: {product.name}")

    await cb_alerts(callback, session, db_user)
