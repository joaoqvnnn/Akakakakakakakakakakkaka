from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from database.models import User, Order, OrderStatus
from keyboards.client import (
    profile_kb,
    order_history_kb,
    edit_profile_kb,
    gift_card_kb,
    main_menu_kb,
)
from services.giftcard import GiftCardService

router = Router(name="profile")


class ProfileStates(StatesGroup):
    waiting_gift = State()
    waiting_whatsapp = State()
    waiting_email = State()


@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery, session: AsyncSession, db_user: User):
    orders_count = (
        await session.execute(
            select(func.count(Order.id)).where(
                Order.user_id == db_user.id,
                Order.status == OrderStatus.DELIVERED,
            )
        )
    ).scalar_one() or 0

    text = (
        f"👤 <b>Meu perfil</b>\n\n"
        f"🔍 Veja aqui os detalhes da sua conta:\n\n"
        f"👤 <b>Informações:</b>\n"
        f"🆔 ID da Carteira: <code>{db_user.id}</code>\n"
        f"💰 Saldo Atual: <b>R$ {db_user.balance:.2f}</b>\n"
        f"📲 Seu Whatsapp: {db_user.whatsapp or 'não informado'}\n\n"
        f"─── 📊 <b>Suas Movimentações:</b>\n"
        f"ー 🛒 Compras Realizadas: <b>{orders_count}</b>\n"
        f"ー 💰 Total Gasto Em Compras: <b>R$ {db_user.total_spent:.2f}</b>\n"
        f"ー 💠 Pix Inseridos: <b>R$ {db_user.total_deposited:.2f}</b>\n"
        f"ー 🎁 Gifts Resgatados: <b>R$ {db_user.total_gifts_redeemed:.2f}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=profile_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "history")
@router.callback_query(F.data == "history_all")
@router.callback_query(F.data.startswith("history_page:"))
async def cb_history(callback: CallbackQuery, session: AsyncSession, db_user: User):
    page = 1
    only_active = callback.data == "history"

    if callback.data.startswith("history_page:"):
        page = int(callback.data.split(":")[1])
        only_active = False

    per_page = 1
    offset = (page - 1) * per_page
    now = datetime.now(timezone.utc)

    q = select(Order).where(
        Order.user_id == db_user.id,
        Order.status == OrderStatus.DELIVERED,
    )
    if only_active:
        q = q.where(
            (Order.expires_at.is_(None)) | (Order.expires_at > now)
        )

    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.execute(count_q)).scalar_one() or 0
    total_pages = max(1, (total + per_page - 1) // per_page)

    result = await session.execute(
        q.order_by(Order.created_at.desc()).offset(offset).limit(per_page)
    )
    orders = list(result.scalars().all())

    if not orders:
        if only_active:
            text = (
                "Você não tem compras ativas (não vencidas) no bot.\n\n"
                "Use o botão abaixo para ver todas as compras."
            )
            await callback.message.edit_text(
                text,
                reply_markup=order_history_kb(1, 1, only_active=True),
                parse_mode="HTML",
            )
        else:
            text = "Você ainda não possui compras no bot."
            await callback.message.edit_text(
                text, reply_markup=profile_kb(), parse_mode="HTML"
            )
        await callback.answer()
        return

    order = orders[0]
    product_name = order.product.name if order.product else "Produto"
    exp = (
        order.expires_at.strftime("%d/%m/%Y")
        if order.expires_at
        else "Sem validade"
    )
    text = (
        f"🛍 <b>Compras:</b> {total}\n\n"
        f"⏰ Data da compra: {order.created_at.strftime('%d/%m/%Y')}\n"
        f"📆 Vencimento: {exp}\n"
        f"💰 Valor: <b>R$ {order.total_price:.2f}</b>\n"
        f"🎫 ID da compra: <code>{order.uuid}</code>\n"
        f"⚜️ Serviço: <b>{product_name}</b>\n"
        f"📧 Email: {order.delivery_email or 'N/A'}\n"
        f"🔐 Entrega:\n<code>{order.delivery_content or 'N/A'}</code>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=order_history_kb(page, total_pages, order.id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "gift_card")
async def cb_gift(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileStates.waiting_gift)
    await callback.message.edit_text(
        "🎁 <b>RESGATAR GIFT CARD</b>\n\n"
        "Digite o código do seu gift card abaixo:\n\n"
        "Exemplo: <code>ABC123XYZ456</code>",
        reply_markup=gift_card_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ProfileStates.waiting_gift)
async def process_gift(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    code = (message.text or "").strip()
    await state.clear()
    try:
        value = await GiftCardService.redeem(session, db_user.id, code)
        await session.refresh(db_user)
        await message.answer(
            f"✅ Gift Card resgatado com sucesso!\n\n"
            f"💰 Valor: <b>R$ {value:.2f}</b>\n"
            f"💳 Novo saldo: <b>R$ {db_user.balance:.2f}</b>",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    except ValueError as e:
        await message.answer(f"❌ {e}", reply_markup=profile_kb())


@router.callback_query(F.data == "edit_profile")
async def cb_edit_profile(callback: CallbackQuery, db_user: User):
    await callback.message.edit_text(
        "✏️ <b>Alterar Dados</b>\n\nSelecione o dado que deseja alterar:",
        reply_markup=edit_profile_kb(db_user.whatsapp),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "edit_whatsapp")
async def cb_edit_whatsapp(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileStates.waiting_whatsapp)
    await callback.message.edit_text(
        "📱 Digite seu WhatsApp (somente números, com DDD):\nEx: <code>449986915568</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ProfileStates.waiting_whatsapp)
async def process_whatsapp(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    raw = "".join(c for c in (message.text or "") if c.isdigit())
    await state.clear()
    if len(raw) < 10:
        await message.answer("❌ Número inválido.")
        return
    db_user.whatsapp = raw
    await message.answer(
        f"✅ WhatsApp salvo: <code>{raw}</code>",
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )


@router.callback_query(F.data == "edit_email")
async def cb_edit_email(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileStates.waiting_email)
    await callback.message.edit_text("📧 Digite seu e-mail:")
    await callback.answer()


@router.message(ProfileStates.waiting_email)
async def process_email(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    email = (message.text or "").strip()
    await state.clear()
    if "@" not in email or "." not in email:
        await message.answer("❌ E-mail inválido.")
        return
    db_user.email = email
    await message.answer(
        f"✅ E-mail salvo: <code>{email}</code>",
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )
