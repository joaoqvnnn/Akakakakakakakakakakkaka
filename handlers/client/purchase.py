from decimal import Decimal

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Product
from keyboards.client import (
    confirm_purchase_kb,
    insufficient_balance_kb,
    quantity_cancel_kb,
    main_menu_kb,
)
from services.purchase import PurchaseService

router = Router(name="purchase")


class BuyStates(StatesGroup):
    waiting_quantity = State()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy_one(callback: CallbackQuery, session: AsyncSession, db_user: User):
    parts = callback.data.split(":")
    product_id = int(parts[1])
    quantity = int(parts[2]) if len(parts) > 2 else 1

    product = await session.get(Product, product_id)
    if not product:
        await callback.answer("Produto não encontrado.", show_alert=True)
        return

    can, msg, missing = await PurchaseService.check_can_buy(
        session, db_user.id, product_id, quantity
    )

    if can:
        total = product.price * quantity
        text = (
            f"💳 <b>Confirmar Compra</b>\n\n"
            f"📦 Produto: <b>{product.name}</b>\n"
            f"🔢 Quantidade: <b>{quantity}</b>\n"
            f"💵 Valor: <b>R$ {total:.2f}</b>\n"
            f"💰 Seu saldo: <b>R$ {db_user.balance:.2f}</b>\n"
            f"💳 Saldo após: <b>R$ {db_user.balance - total:.2f}</b>\n\n"
            f"Deseja confirmar?"
        )
        await callback.message.edit_text(
            text,
            reply_markup=confirm_purchase_kb(product_id, quantity),
            parse_mode="HTML",
        )
    else:
        if "Estoque" in msg:
            await callback.answer(msg, show_alert=True)
            return
        total = product.price * quantity
        text = (
            f"❌ <b>Saldo insuficiente!</b>\n\n"
            f"💰 Seu saldo: <b>R$ {db_user.balance:.2f}</b>\n"
            f"💵 Valor do produto: <b>R$ {total:.2f}</b>\n"
            f"📉 Faltam: <b>R$ {missing:.2f}</b>\n\n"
            f"💡 Deseja gerar um PIX no valor de <b>R$ {missing:.2f}</b> "
            f"para completar a compra?"
        )
        await callback.message.edit_text(
            text,
            reply_markup=insufficient_balance_kb(
                product_id, float(missing), quantity
            ),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_buy:"))
async def cb_confirm_buy(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    parts = callback.data.split(":")
    product_id = int(parts[1])
    quantity = int(parts[2])

    try:
        order, contents = await PurchaseService.buy_with_balance(
            session, db_user.id, product_id, quantity
        )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    product = await session.get(Product, product_id)
    delivery = "\n".join(contents)
    text = (
        f"✅ <b>COMPRA APROVADA!</b>\n\n"
        f"🎬 Produto: <b>{product.name if product else '—'}</b>\n"
        f"💰 Valor: <b>R$ {order.total_price:.2f}</b>\n"
        f"📅 Data: {order.created_at.strftime('%d/%m/%Y %H:%M')}\n"
        f"💳 Pagamento: Saldo\n"
        f"📦 Sua entrega está pronta:\n\n"
        f"<code>{delivery}</code>\n\n"
        f"🛡 Guarde esses dados com segurança!"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📧 Receber por E-mail",
            callback_data=f"order_email:{order.id}",
        ),
        InlineKeyboardButton(
            text="📲 Receber por WhatsApp",
            callback_data=f"order_whatsapp:{order.id}",
        ),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Menu", callback_data="main_menu")
    )

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer("✅ Compra realizada!")


@router.callback_query(F.data.startswith("buy_multi:"))
async def cb_buy_multi(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    product_id = int(callback.data.split(":")[1])
    product = await session.get(Product, product_id)
    stock = product.stock_count if product else 0

    await state.set_state(BuyStates.waiting_quantity)
    await state.update_data(product_id=product_id)

    await callback.message.edit_text(
        f"📦 <b>Quantos logins deseja comprar?</b>\n\n"
        f"📦 Estoque disponível: <b>{stock}</b>\n\n"
        f"💡 Digite /cancelar a qualquer momento para sair.",
        reply_markup=quantity_cancel_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(BuyStates.waiting_quantity)
async def process_quantity(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
):
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Compra cancelada.", reply_markup=main_menu_kb())
        return

    try:
        quantity = int((message.text or "").strip())
        if quantity < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Digite um número válido maior que zero.")
        return

    data = await state.get_data()
    product_id = data["product_id"]
    await state.clear()

    product = await session.get(Product, product_id)
    if not product:
        await message.answer("❌ Produto não encontrado.")
        return

    can, msg, missing = await PurchaseService.check_can_buy(
        session, db_user.id, product_id, quantity
    )

    if not can and "Estoque" in msg:
        await message.answer(f"❌ {msg}")
        return

    total = product.price * quantity
    if can:
        text = (
            f"💳 <b>Confirmar Compra</b>\n\n"
            f"📦 Produto: <b>{product.name}</b>\n"
            f"🔢 Quantidade: <b>{quantity}</b>\n"
            f"💵 Valor total: <b>R$ {total:.2f}</b>\n"
            f"💰 Seu saldo: <b>R$ {db_user.balance:.2f}</b>"
        )
        await message.answer(
            text,
            reply_markup=confirm_purchase_kb(product_id, quantity),
            parse_mode="HTML",
        )
    else:
        text = (
            f"❌ <b>Saldo insuficiente!</b>\n\n"
            f"💰 Seu saldo: <b>R$ {db_user.balance:.2f}</b>\n"
            f"💵 Valor total: <b>R$ {total:.2f}</b>\n"
            f"📉 Faltam: <b>R$ {missing:.2f}</b>\n\n"
            f"💡 Deseja gerar um PIX para completar a compra?"
        )
        await message.answer(
            text,
            reply_markup=insufficient_balance_kb(
                product_id, float(missing), quantity
            ),
            parse_mode="HTML",
        )
