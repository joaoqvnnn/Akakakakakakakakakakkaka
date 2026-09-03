from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Order, OrderStatus, GiftCardRedemption, Product
from keyboards.client_dynamic import (
    profile_kb,
    order_history_kb,
    gift_card_kb,
    edit_profile_kb,
)
from services.giftcard import GiftCardService
from utils.validators import is_valid_email
from utils.phone import normalize_phone_flexible, is_valid_phone_flexible

router = Router(name="profile")


class ProfileStates(StatesGroup):
    gift_code = State()
    whatsapp = State()
    email = State()


@router.callback_query(F.data == "profile")
async def cb_profile(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    purchases = (
        await session.execute(
            select(func.count(Order.id)).where(
                Order.user_id == db_user.id,
                Order.status == OrderStatus.DELIVERED,
            )
        )
    ).scalar_one() or 0

    gifts = (
        await session.execute(
            select(func.coalesce(func.sum(GiftCardRedemption.amount), 0)).where(
                GiftCardRedemption.user_id == db_user.id
            )
        )
    ).scalar_one() or 0

    text = (
        f"👤 <b>Meu perfil</b>\n\n"
        f"🔍 Veja aqui os detalhes da sua conta:\n\n"
        f"— 👤 Informações:\n"
        f"🆔 ID da Carteira: <code>{db_user.id}</code>\n"
        f"💰 Saldo Atual: <b>R$ {db_user.balance:.2f}</b>\n"
        f"📲 Seu Whatsapp: {db_user.whatsapp or 'não informado'}\n\n"
        f"─── 📊 Suas Movimentações:\n"
        f"— 🛒 Compras Realizadas: <b>{purchases}</b>\n"
        f"— 💰 Total Gasto Em Compras: <b>R$ {db_user.total_spent:.2f}</b>\n"
        f"— 💠 Pix Inseridos: <b>R$ {db_user.total_deposited:.2f}</b>\n"
        f"— 🎁 Gifts Resgatados: <b>R$ {float(gifts):.2f}</b>"
    )
    kb = await profile_kb(session)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.in_({"history", "history_all"}))
async def cb_history(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    only_active = callback.data == "history"
    await _show_history(callback, session, db_user, page=1, only_active=only_active)


@router.callback_query(F.data.startswith("history_page:"))
async def cb_history_page(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    page = int(callback.data.split(":")[1])
    await _show_history(callback, session, db_user, page=page, only_active=False)


async def _show_history(callback, session, db_user, page=1, only_active=True):
    result = await session.execute(
        select(Order)
        .where(
            Order.user_id == db_user.id,
            Order.status == OrderStatus.DELIVERED,
        )
        .order_by(Order.created_at.desc())
    )
    orders = list(result.scalars().all())

    if only_active:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        active = [
            o
            for o in orders
            if (o.expires_at and o.expires_at > now) or not o.expires_at
        ]
        if not active:
            kb = await order_history_kb(session, 1, 1, 0, True)
            # teclado mínimo só com ver todas
            from aiogram.types import InlineKeyboardButton
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from services.buttons import ButtonService

            all_txt = await ButtonService.get(session, "btn_history_all")
            back = await ButtonService.get(session, "btn_back")
            b = InlineKeyboardBuilder()
            b.row(InlineKeyboardButton(text=all_txt, callback_data="history_all"))
            b.row(InlineKeyboardButton(text=back, callback_data="profile"))
            await callback.message.edit_text(
                "Você não tem compras ativas (não vencidas) no bot.\n\n"
                "Use o botão abaixo para ver todas as compras.",
                reply_markup=b.as_markup(),
            )
            await callback.answer()
            return
        orders = active

    if not orders:
        kb = await profile_kb(session)
        await callback.message.edit_text(
            "Nenhuma compra encontrada.", reply_markup=kb
        )
        await callback.answer()
        return

    total = len(orders)
    page = max(1, min(page, total))
    order = orders[page - 1]
    product_name = "Produto"
    if order.product_id:
        p = await session.get(Product, order.product_id)
        if p:
            product_name = p.name

    exp = order.expires_at.strftime("%d/%m/%Y") if order.expires_at else "—"
    text = (
        f"🛍 Compras: {total}\n\n"
        f"⏰ Data da compra: {order.created_at.strftime('%d/%m/%Y')}\n"
        f"📆 Vencimento: {exp}\n"
        f"💰 Valor: R$ {order.total_price:.2f}\n"
        f"🎫 ID da compra: <code>{order.uuid}</code>\n"
        f"⚜️ Serviço: {product_name}\n"
        f"📦 Entrega:\n<code>{order.delivery_content or 'N/A'}</code>"
    )
    kb = await order_history_kb(session, page, total, order.id, only_active)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "gift_card")
async def cb_gift(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.set_state(ProfileStates.gift_code)
    kb = await gift_card_kb(session)
    await callback.message.edit_text(
        "🎁 <b>RESGATAR GIFT CARD</b>\n\n"
        "Digite o código do seu gift card abaixo:\n\n"
        "Exemplo: ABC123XYZ456",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ProfileStates.gift_code)
async def process_gift(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    code = (message.text or "").strip()
    await state.clear()
    try:
        value = await GiftCardService.redeem(session, db_user.id, code)
        await session.refresh(db_user)
        await message.answer(
            f"✅ Gift resgatado! +R$ {value:.2f}\n"
            f"💰 Saldo: R$ {db_user.balance:.2f}",
            reply_markup=await profile_kb(session),
        )
    except ValueError as e:
        await message.answer(
            f"❌ {e}", reply_markup=await profile_kb(session)
        )


@router.callback_query(F.data == "edit_profile")
async def cb_edit_profile(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    kb = await edit_profile_kb(session, db_user.whatsapp)
    await callback.message.edit_text(
        "✏️ <b>Alterar Dados</b>\n\nSelecione o dado que deseja alterar:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "edit_whatsapp")
async def cb_edit_wa(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileStates.whatsapp)
    await callback.message.edit_text(
        "📲 Digite o WhatsApp (com ou sem máscara):\nEx: 449986915568 ou (44) 99869-1556"
    )
    await callback.answer()


@router.message(ProfileStates.whatsapp)
async def process_wa(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    raw = message.text or ""
    await state.clear()
    if not is_valid_phone_flexible(raw):
        await message.answer(
            "❌ Número inválido.", reply_markup=await profile_kb(session)
        )
        return
    phone = normalize_phone_flexible(raw)
    db_user.whatsapp = phone
    await message.answer(
        f"✅ WhatsApp salvo: <code>{phone}</code>",
        parse_mode="HTML",
        reply_markup=await profile_kb(session),
    )


@router.callback_query(F.data == "edit_email")
async def cb_edit_email(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileStates.email)
    await callback.message.edit_text("📧 Digite seu e-mail:")
    await callback.answer()


@router.message(ProfileStates.email)
async def process_email(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    email = (message.text or "").strip()
    await state.clear()
    if not is_valid_email(email):
        await message.answer(
            "❌ E-mail inválido.", reply_markup=await profile_kb(session)
        )
        return
    db_user.email = email
    await message.answer(
        f"✅ E-mail salvo: <code>{email}</code>",
        parse_mode="HTML",
        reply_markup=await profile_kb(session),
    )
