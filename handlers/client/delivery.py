from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Order
from keyboards.client import main_menu_kb, profile_kb

router = Router(name="delivery")


class DeliveryStates(StatesGroup):
    waiting_email = State()
    waiting_whatsapp = State()


@router.callback_query(F.data.startswith("order_email:"))
async def cb_order_email(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(DeliveryStates.waiting_email)
    await state.update_data(order_id=order_id)
    await callback.message.answer(
        "📧 Digite o e-mail para receber os dados da compra:"
    )
    await callback.answer()


@router.message(DeliveryStates.waiting_email)
async def process_order_email(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    email = (message.text or "").strip()
    data = await state.get_data()
    await state.clear()

    if "@" not in email or "." not in email:
        await message.answer("❌ E-mail inválido.")
        return

    order = await session.get(Order, data.get("order_id"))
    if not order or order.user_id != db_user.id:
        await message.answer("❌ Pedido não encontrado.")
        return

    order.delivery_email = email
    db_user.email = email

    # Envio real de e-mail: plugar SMTP/API depois (SendGrid, etc.)
    # Por enquanto confirma e guarda no banco.
    await message.answer(
        f"✅ E-mail salvo: <code>{email}</code>\n\n"
        f"📦 Dados do pedido <code>{order.uuid}</code>:\n"
        f"<code>{order.delivery_content or '—'}</code>\n\n"
        f"(O envio automático por e-mail será ligado na config de SMTP do admin.)",
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )


@router.callback_query(F.data.startswith("order_whatsapp:"))
async def cb_order_whatsapp(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(DeliveryStates.waiting_whatsapp)
    await state.update_data(order_id=order_id)
    await callback.message.answer(
        "📲 Digite o WhatsApp (somente números com DDD):\nEx: <code>449986915568</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(DeliveryStates.waiting_whatsapp)
async def process_order_whatsapp(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    raw = "".join(c for c in (message.text or "") if c.isdigit())
    data = await state.get_data()
    await state.clear()

    if len(raw) < 10:
        await message.answer("❌ Número inválido.")
        return

    order = await session.get(Order, data.get("order_id"))
    if not order or order.user_id != db_user.id:
        await message.answer("❌ Pedido não encontrado.")
        return

    order.delivery_whatsapp = raw
    db_user.whatsapp = raw

    await message.answer(
        f"✅ WhatsApp salvo: <code>{raw}</code>\n\n"
        f"📦 Dados:\n<code>{order.delivery_content or '—'}</code>\n\n"
        f"(Envio via WhatsApp Business/API será ligado na config do admin.)",
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )


@router.callback_query(F.data.startswith("order_pdf:"))
async def cb_order_pdf(callback: CallbackQuery, session: AsyncSession, db_user: User):
    order_id = int(callback.data.split(":")[1])
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer("Pedido não encontrado.", show_alert=True)
        return

    # PDF real pode ser gerado com reportlab depois; por ora envia comprovante em texto
    text = (
        f"📄 <b>Comprovante #{order.uuid}</b>\n\n"
        f"Produto ID: {order.product_id}\n"
        f"Valor: R$ {order.total_price:.2f}\n"
        f"Data: {order.created_at.strftime('%d/%m/%Y %H:%M')}\n"
        f"Status: {order.status.value}\n\n"
        f"<code>{order.delivery_content or '—'}</code>"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
