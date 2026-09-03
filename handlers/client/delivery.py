from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Order, Product
from keyboards.client import profile_kb, main_menu_kb
from services.settings_service import SettingsService
from services.messages import MessageService
from services.email_smtp import EmailService
from services.whatsapp_baileys import WhatsAppBaileysService, normalize_phone
from services.whatsapp_order_flow import WhatsAppOrderFlow
from utils.validators import is_valid_email

router = Router(name="delivery")


class DeliveryStates(StatesGroup):
    waiting_email = State()
    waiting_whatsapp = State()
    confirm_whatsapp = State()
    waiting_release_password = State()


@router.callback_query(F.data.startswith("order_email:"))
async def cb_order_email(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
):
    order_id = int(callback.data.split(":")[1])
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer("Pedido não encontrado.", show_alert=True)
        return
    await state.set_state(DeliveryStates.waiting_email)
    await state.update_data(order_id=order_id)
    hint = f"\nAtual: <code>{db_user.email}</code>" if db_user.email else ""
    await callback.message.answer(
        f"📧 Digite o e-mail para receber a compra:{hint}",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(DeliveryStates.waiting_email)
async def process_order_email(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    email = (message.text or "").strip()
    data = await state.get_data()
    await state.clear()
    if not is_valid_email(email):
        await message.answer("❌ E-mail inválido.")
        return
    order = await session.get(Order, data.get("order_id"))
    if not order or order.user_id != db_user.id:
        await message.answer("❌ Pedido não encontrado.")
        return
    order.delivery_email = email
    db_user.email = email
    product = await session.get(Product, order.product_id)
    product_name = product.name if product else "Produto"
    activation = (await MessageService.get_rendered(session, "delivery_activation_help"))["content"]
    support = await SettingsService.get(session, "support_link", settings.SUPPORT_LINK)
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    body = (
        await MessageService.get_rendered(
            session,
            "delivery_email",
            store_name=store,
            product_name=product_name,
            price=f"{order.total_price:.2f}",
            date=order.created_at.strftime("%d/%m/%Y %H:%M:%S"),
            payment_method=order.payment_method.value,
            order_id=order.uuid,
            delivery=order.delivery_content or "—",
            activation_help=activation,
            support_link=support,
        )
    )["content"]
    sent = await EmailService.send(
        session, email, f"Sua compra — {product_name} | {store}", body
    )
    if sent:
        await message.answer(
            f"✅ E-mail enviado para <code>{email}</code>",
            parse_mode="HTML",
            reply_markup=profile_kb(),
        )
    else:
        await message.answer(
            f"📧 Salvo: <code>{email}</code>\n\n<code>{body[:3000]}</code>",
            parse_mode="HTML",
            reply_markup=profile_kb(),
        )


@router.callback_query(F.data.startswith("order_whatsapp:"))
async def cb_order_whatsapp(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
):
    order_id = int(callback.data.split(":")[1])
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer("Pedido não encontrado.", show_alert=True)
        return
    await state.set_state(DeliveryStates.waiting_whatsapp)
    await state.update_data(order_id=order_id)
    hint = ""
    if db_user.whatsapp:
        hint = (
            f"\n\nSalvo: <code>{db_user.whatsapp}</code>\n"
            f"Envie outro ou digite <code>ok</code>."
        )
    await callback.message.answer(
        f"📲 WhatsApp (DDI+DDD+número):{hint}",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(DeliveryStates.waiting_whatsapp)
async def process_whatsapp_number(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    data = await state.get_data()
    order = await session.get(Order, data.get("order_id"))
    if not order or order.user_id != db_user.id:
        await state.clear()
        await message.answer("❌ Pedido não encontrado.")
        return

    raw = (message.text or "").strip()
    if raw.lower() == "ok" and db_user.whatsapp:
        phone = db_user.whatsapp
    else:
        phone = normalize_phone(raw)
        if len(phone) < 12:
            await message.answer("❌ Número inválido. Ex: 5544999999999")
            return

    order.delivery_whatsapp = phone
    db_user.whatsapp = phone
    await state.update_data(order_id=order.id, phone=phone)

    product = await session.get(Product, order.product_id)
    product_name = product.name if product else "Produto"
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    image_url = await SettingsService.get(session, "delivery_whatsapp_image_url") or None
    wa_tpl = await MessageService.get_rendered(
        session,
        "delivery_whatsapp",
        store_name=store,
        product_name=product_name,
        price=f"{order.total_price:.2f}",
        date=order.created_at.strftime("%d/%m/%Y %H:%M:%S"),
        payment_method=order.payment_method.value,
        order_id=order.uuid,
        delivery="",
        activation_help="",
        support_link=await SettingsService.get(session, "support_link"),
    )

    sent = await WhatsAppBaileysService.send_delivery_preview(
        session=session,
        phone=phone,
        product_name=product_name,
        price=f"{order.total_price:.2f}",
        date_str=order.created_at.strftime("%d/%m/%Y %H:%M:%S"),
        payment_method=order.payment_method.value,
        order_id=order.uuid,
        store_name=store,
        image_url=image_url,
        extra_caption=wa_tpl["content"],
        order_db_id=order.id,
    )

    # backup no Telegram (se Baileys falhar botões)
    await state.set_state(DeliveryStates.confirm_whatsapp)
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✅ Confirmar e liberar (Telegram)",
            callback_data=f"wa_confirm:{order.id}",
        )
    )
    b.row(
        InlineKeyboardButton(
            text="✏️ Corrigir número", callback_data=f"wa_edit_phone:{order.id}"
        )
    )
    b.row(InlineKeyboardButton(text="❌ Cancelar", callback_data="main_menu"))

    status = (
        "✅ WhatsApp: resumo + botão *Confirmar* enviados.\n"
        "No WhatsApp: toque em Confirmar → digite a senha de liberação."
        if sent
        else "⚠️ Baileys offline. Você ainda pode confirmar pelo Telegram."
    )
    await message.answer(
        f"{status}\n\nNúmero: <code>{phone}</code>\nProduto: <b>{product_name}</b>",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("wa_edit_phone:"))
async def cb_edit_phone(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(DeliveryStates.waiting_whatsapp)
    await state.update_data(order_id=order_id)
    await callback.message.answer("📲 Digite o número correto:")
    await callback.answer()


@router.callback_query(F.data.startswith("wa_confirm:"))
async def cb_wa_confirm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
):
    order_id = int(callback.data.split(":")[1])
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer("Pedido inválido.", show_alert=True)
        return

    if await SettingsService.get_bool(session, "delivery_password_enabled"):
        await state.set_state(DeliveryStates.waiting_release_password)
        await state.update_data(order_id=order_id)
        await callback.message.answer(
            "🔐 Digite a <b>senha de liberação</b>.\n"
            "Errada = dados não vão no WhatsApp.",
            parse_mode="HTML",
        )
        await callback.answer()
        return

    ok = await _release_to_whatsapp(session, order)
    await state.clear()
    await callback.message.answer(
        "✅ Acesso enviado no WhatsApp." if ok else "⚠️ Falha no WhatsApp. Veja o Histórico.",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.message(DeliveryStates.waiting_release_password)
async def process_release_password(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    data = await state.get_data()
    order = await session.get(Order, data.get("order_id"))
    await state.clear()
    if not order or order.user_id != db_user.id:
        await message.answer("❌ Pedido não encontrado.")
        return
    expected = await SettingsService.get(session, "delivery_password")
    if (message.text or "").strip() != expected:
        await message.answer(
            "❌ Senha incorreta. Produto não liberado.",
            reply_markup=main_menu_kb(),
        )
        return
    ok = await _release_to_whatsapp(session, order)
    if ok:
        await message.answer(
            "✅ Senha correta. Login enviado no WhatsApp.",
            reply_markup=main_menu_kb(),
        )
    else:
        await message.answer(
            f"✅ Senha correta.\n<code>{order.delivery_content or '—'}</code>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )


async def _release_to_whatsapp(session: AsyncSession, order: Order) -> bool:
    product = await session.get(Product, order.product_id)
    product_name = product.name if product else "Produto"
    if not order.delivery_whatsapp:
        return False
    activation = (await MessageService.get_rendered(session, "delivery_activation_help"))[
        "content"
    ]
    return await WhatsAppBaileysService.send_credentials(
        session,
        order.delivery_whatsapp,
        product_name,
        order.delivery_content or "—",
        activation_help=activation,
    )


@router.callback_query(F.data.startswith("order_pdf:"))
async def cb_order_pdf(callback: CallbackQuery, session: AsyncSession, db_user: User):
    order_id = int(callback.data.split(":")[1])
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer("Pedido não encontrado.", show_alert=True)
        return
    await callback.message.answer(
        f"📄 <b>Comprovante</b>\n"
        f"ID: <code>{order.uuid}</code>\n"
        f"Valor: R$ {order.total_price:.2f}\n"
        f"Data: {order.created_at.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        f"<code>{order.delivery_content or '—'}</code>",
        parse_mode="HTML",
    )
    await callback.answer()
