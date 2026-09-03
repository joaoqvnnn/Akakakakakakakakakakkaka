from decimal import Decimal

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Product, ProductStatus
from keyboards.client_dynamic import (
    confirm_purchase_kb,
    insufficient_balance_kb,
    quantity_cancel_kb,
    main_menu_kb,
    pix_created_kb,
    delivery_after_buy_kb,
)
from services.purchase import PurchaseService
from services.payment import PaymentService
from services.messages import MessageService
from services.settings_service import SettingsService

router = Router(name="purchase")
payment_service = PaymentService()


class BuyStates(StatesGroup):
    waiting_quantity = State()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy_one(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    parts = callback.data.split(":")
    product_id = int(parts[1])
    quantity = int(parts[2]) if len(parts) > 2 else 1

    product = await session.get(Product, product_id)
    if not product or product.status != ProductStatus.ACTIVE:
        await callback.answer("Produto indisponível.", show_alert=True)
        return

    total = product.price * quantity
    can, reason = await PurchaseService.check_can_buy(
        session, db_user.id, product_id, quantity
    )

    if can:
        text = (
            f"🛒 <b>Confirmar compra</b>\n\n"
            f"{product.emoji} <b>{product.name}</b>\n"
            f"Qtd: <b>{quantity}</b>\n"
            f"Total: <b>R$ {total:.2f}</b>\n"
            f"Seu saldo: <b>R$ {db_user.balance:.2f}</b>"
        )
        kb = await confirm_purchase_kb(session, product_id, quantity)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        return

    if "estoque" in reason.lower():
        await callback.answer(reason, show_alert=True)
        return

    missing = total - db_user.balance
    if missing < 0:
        missing = total

    tpl = await MessageService.get_rendered(
        session,
        "insufficient_balance",
        balance=f"{db_user.balance:.2f}",
        price=f"{total:.2f}",
        missing=f"{missing:.2f}",
    )
    kb = await insufficient_balance_kb(
        session, product_id, float(missing), quantity
    )
    await callback.message.edit_text(
        tpl["content"], reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_multi:"))
async def cb_buy_multi(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    product_id = int(callback.data.split(":")[1])
    product = await session.get(Product, product_id)
    if not product:
        await callback.answer("Produto não encontrado.", show_alert=True)
        return

    await state.set_state(BuyStates.waiting_quantity)
    await state.update_data(product_id=product_id)
    kb = await quantity_cancel_kb(session)
    await callback.message.edit_text(
        f"🛒 <b>Quantos logins deseja comprar?</b>\n\n"
        f"📦 Estoque disponível: <b>{product.stock_count}</b>\n\n"
        f"💡 Digite /cancelar a qualquer momento para sair.",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(BuyStates.waiting_quantity)
async def process_quantity(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer(
            "❌ Cancelado.", reply_markup=await main_menu_kb(session)
        )
        return

    try:
        quantity = int((message.text or "").strip())
        if quantity < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Digite um número válido.")
        return

    data = await state.get_data()
    product_id = data["product_id"]
    product = await session.get(Product, product_id)
    if not product:
        await state.clear()
        await message.answer("❌ Produto não encontrado.")
        return

    if quantity > (product.stock_count or 0):
        await message.answer(
            f"❌ Estoque insuficiente. Disponível: {product.stock_count}"
        )
        return

    await state.clear()
    total = product.price * quantity
    can, reason = await PurchaseService.check_can_buy(
        session, db_user.id, product_id, quantity
    )

    if can:
        text = (
            f"🛒 <b>Confirmar compra</b>\n\n"
            f"{product.emoji} <b>{product.name}</b>\n"
            f"Qtd: <b>{quantity}</b>\n"
            f"Total: <b>R$ {total:.2f}</b>\n"
            f"Seu saldo: <b>R$ {db_user.balance:.2f}</b>"
        )
        kb = await confirm_purchase_kb(session, product_id, quantity)
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    missing = total - db_user.balance
    if missing < 0:
        missing = total
    tpl = await MessageService.get_rendered(
        session,
        "insufficient_balance",
        balance=f"{db_user.balance:.2f}",
        price=f"{total:.2f}",
        missing=f"{missing:.2f}",
    )
    kb = await insufficient_balance_kb(
        session, product_id, float(missing), quantity
    )
    await message.answer(tpl["content"], reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_buy:"))
async def cb_confirm_buy(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    parts = callback.data.split(":")
    product_id = int(parts[1])
    quantity = int(parts[2]) if len(parts) > 2 else 1

    try:
        order = await PurchaseService.buy_with_balance(
            session, db_user.id, product_id, quantity
        )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    product = await session.get(Product, product_id)
    product_name = product.name if product else "Produto"
    date_str = order.created_at.strftime("%d/%m/%Y %H:%M:%S")

    tpl = await MessageService.get_rendered(
        session,
        "purchase_success",
        product_name=product_name,
        price=f"{order.total_price:.2f}",
        date=date_str,
        payment_method=order.payment_method.value,
        delivery=order.delivery_content or "—",
    )
    kb = await delivery_after_buy_kb(session, order.id)
    await callback.message.edit_text(
        tpl["content"], reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer("✅ Compra realizada!")


@router.callback_query(F.data.startswith("pix_for_product:"))
async def cb_pix_for_product(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    parts = callback.data.split(":")
    product_id = int(parts[1])
    quantity = int(parts[2])
    amount = Decimal(parts[3])

    await callback.message.edit_text("⏳ Gerando pagamento...")

    try:
        payment, qr_b64, copy_paste = await payment_service.create_pix(
            session,
            user_id=db_user.id,
            amount=amount,
            description=f"Compra produto #{product_id} x{quantity}",
            metadata={
                "product_id": product_id,
                "quantity": quantity,
                "purpose": "product_completion",
            },
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Erro ao gerar PIX: {e}",
            reply_markup=await main_menu_kb(session),
        )
        await callback.answer()
        return

    exp = await SettingsService.get(session, "pix_expiration_minutes")
    text = (
        f"💰 <b>Comprar Saldo com Pix Automático</b>\n\n"
        f"⏱️ Expira em: <b>{exp} Minutos</b>\n"
        f"💵 Valor: <b>R$ {payment.amount:.2f}</b>\n"
        f"✨ ID da Recarga: <code>{payment.uuid}</code>\n\n"
        f"📃 Atenção: Este código é válido para apenas um único pagamento.\n\n"
        f"💎 <b>Pix Copia e Cola:</b>\n"
        f"<code>{copy_paste or payment.copy_paste or '—'}</code>\n\n"
        f"💡 Clique no código acima para copiar.\n\n"
        f"📊 Dados:\n"
        f"— 💰 Saldo Atual: R$ {db_user.balance:.2f}\n"
        f"— 🎁 Bônus à receber: R$ 0,00\n"
        f"— 💸 Saldo após o pagamento: R$ {db_user.balance + payment.amount:.2f}\n\n"
        f"🇧🇷 Após o pagamento, seu saldo será liberado instantaneamente."
    )
    kb = await pix_created_kb(session, payment.uuid)

    if payment.qr_code_base64 or qr_b64:
        import base64
        from aiogram.types import BufferedInputFile

        raw = payment.qr_code_base64 or qr_b64
        if "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            photo = BufferedInputFile(base64.b64decode(raw), filename="qr.png")
            await callback.message.delete()
            await callback.message.answer_photo(
                photo, caption=text, reply_markup=kb, parse_mode="HTML"
            )
            await callback.answer()
            return
        except Exception:
            pass

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
