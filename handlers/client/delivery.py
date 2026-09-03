from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Order, Product
from keyboards.client_dynamic import main_menu_kb, profile_kb
from services.settings_service import SettingsService
from services.messages import MessageService
from services.email_smtp import EmailService
from services.whatsapp_baileys import WhatsAppBaileysService, normalize_phone
from services.order_secure_link import OrderSecureService
from services.buttons import ButtonService
from utils.validators import is_valid_email
from utils.phone import normalize_phone_flexible, is_valid_phone_flexible

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
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    support = await SettingsService.get(session, "support_link", settings.SUPPORT_LINK)
    activation = (
        await MessageService.get_rendered(session, "delivery_activation_help")
    )["content"]
    secure_url = OrderSecureService.public_url(order.uuid)

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
            delivery=(
                "Por segurança o login não vai em texto no e-mail.\n"
                f"Abra o link e digite sua senha:\n{secure_url}"
            ),
            activation_help=activation,
            support_link=support,
        )
    )["content"]
    body += f"\n\nVencimento: {order.expires_at.strftime('%d/%m/%Y') if order.expires_at else '—'}"
    body += f"\nAcessar pedido: {secure_url}"

    sent = await EmailService.send(
        session, email, f"Compra — {product_name} | {store}", body
    )
    kb = await profile_kb(session)
    await message.answer(
        (
            f"✅ E-mail enviado para <code>{email}</code>\n"
            if sent
            else f"📧 Salvo (SMTP off).\n"
        )
        + f"🔗 {secure_url}",
        parse_mode="HTML",
        reply_markup=kb,
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
        f"📲 WhatsApp (qualquer formato):{hint}",
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
        if not is_valid_phone_flexible(raw):
            await message.answer("❌ Número inválido.")
            return
        phone = normalize_phone_flexible(raw)

    order.delivery_whatsapp = phone
    db_user.whatsapp = phone

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

    await state.set_state(DeliveryStates.confirm_whatsapp)
    await state.update_data(order_id=order.id, phone=phone)

    conf = await ButtonService.get(session, "btn_wa_confirm")
    edit = await ButtonService.get(session, "btn_wa_edit_phone")
    cancel = await ButtonService.get(session, "btn_cancel_buy")
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=conf, callback_data=f"wa_confirm:{order.id}")
    )
    b.row(
        InlineKeyboardButton(text=edit, callback_data=f"wa_edit_phone:{order.id}")
    )
    b.row(InlineKeyboardButton(text=cancel, callback_data="main_menu"))

    status = (
        "✅ WhatsApp: resumo + botão Confirmar enviados.\n"
        "No WA: Confirmar → digite a senha."
        if sent
        else "⚠️ Baileys offline. Confirme pelo Telegram."
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
    kb = await main_menu_kb(session)
    await callback.message.answer(
        "✅ Acesso enviado no WhatsApp." if ok else "⚠️ Falha no WhatsApp.",
        reply_markup=kb,
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
    fallback_ok = OrderSecureService.check_user_password(
        db_user, (message.text or "").strip(), expected or "1234"
    )
    if not fallback_ok and (message.text or "").strip() != expected:
        kb = await main_menu_kb(session)
        await message.answer(
            "❌ Senha incorreta. Produto não liberado.", reply_markup=kb
        )
        return

    ok = await _release_to_whatsapp(session, order)
    kb = await main_menu_kb(session)
    if ok:
        await message.answer(
            "✅ Senha correta. Login enviado no WhatsApp.", reply_markup=kb
        )
    else:
        await message.answer(
            f"✅ Senha correta.\n<code>{order.delivery_content or '—'}</code>",
            parse_mode="HTML",
            reply_markup=kb,
        )


async def _release_to_whatsapp(session: AsyncSession, order: Order) -> bool:
    product = await session.get(Product, order.product_id)
    product_name = product.name if product else "Produto"
    if not order.delivery_whatsapp:
        return False
    activation = (
        await MessageService.get_rendered(session, "delivery_activation_help")
    )["content"]
    return await WhatsAppBaileysService.send_credentials(
        session,
        order.delivery_whatsapp,
        product_name,
        order.delivery_content or "—",
        activation_help=activation,
    )


@router.callback_query(F.data.startswith("order_show:"))
async def cb_order_show(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    order_id = int(callback.data.split(":")[1])
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer("Pedido não encontrado.", show_alert=True)
        return
    await callback.message.answer(
        f"👁 <b>Dados no Telegram</b>\n\n"
        f"<code>{order.delivery_content or '—'}</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("order_pdf:"))
async def cb_order_pdf(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    order_id = int(callback.data.split(":")[1])
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer("Pedido não encontrado.", show_alert=True)
        return
    url = OrderSecureService.public_url(order.uuid)
    await callback.message.answer(
        f"📄 Abra o link seguro, digite a senha e baixe o PDF:\n{url}"
    )
    await callback.answer()
