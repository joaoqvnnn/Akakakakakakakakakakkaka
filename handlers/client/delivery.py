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
from services.whatsapp_baileys import WhatsAppBaileysService, normalize_phone

router = Router(name="delivery")


class DeliveryStates(StatesGroup):
    waiting_email = State()
    waiting_whatsapp = State()
    confirm_whatsapp = State()
    waiting_release_password = State()
    edit_whatsapp = State()
    edit_email = State()


def _order_kb(order_id: int) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="📧 Receber por E-mail", callback_data=f"order_email:{order_id}"
        ),
        InlineKeyboardButton(
            text="📲 Receber por WhatsApp", callback_data=f"order_whatsapp:{order_id}"
        ),
    )
    b.row(InlineKeyboardButton(text="🏠 Menu", callback_data="main_menu"))
    return b


# ---------- E-MAIL ----------

@router.callback_query(F.data.startswith("order_email:"))
async def cb_order_email(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    order_id = int(callback.data.split(":")[1])
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer("Pedido não encontrado.", show_alert=True)
        return

    await state.set_state(DeliveryStates.waiting_email)
    await state.update_data(order_id=order_id)

    hint = f"\nAtual: <code>{db_user.email}</code>" if db_user.email else ""
    await callback.message.answer(
        f"📧 Digite o e-mail para receber os dados da compra:{hint}\n\n"
        f"Se estiver errado, envie o correto agora.",
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

    if "@" not in email or "." not in email:
        await message.answer("❌ E-mail inválido. Tente de novo pelo histórico.")
        return

    order = await session.get(Order, data.get("order_id"))
    if not order or order.user_id != db_user.id:
        await message.answer("❌ Pedido não encontrado.")
        return

    order.delivery_email = email
    db_user.email = email

    product = await session.get(Product, order.product_id)
    product_name = product.name if product else "Produto"
    activation = (
        await MessageService.get_rendered(session, "delivery_activation_help")
    )["content"]
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

    # Envio SMTP real: ligar depois com config smtp_*
    # Por enquanto entrega o texto no Telegram (cópia do e-mail)
    await message.answer(
        f"✅ E-mail registrado: <code>{email}</code>\n\n"
        f"📄 <b>Conteúdo que será enviado por e-mail:</b>\n\n"
        f"<code>{body[:3500]}</code>",
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )


# ---------- WHATSAPP: número → preview Baileys → confirmar → senha → credenciais ----------

@router.callback_query(F.data.startswith("order_whatsapp:"))
async def cb_order_whatsapp(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
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
            f"\n\nNúmero salvo: <code>{db_user.whatsapp}</code>\n"
            f"Envie outro se quiser corrigir, ou envie <code>ok</code> para usar este."
        )
    await callback.message.answer(
        f"📲 Digite o WhatsApp (DDI+DDD+número, só números):\n"
        f"Ex: <code>55449986915568</code>{hint}",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(DeliveryStates.waiting_whatsapp)
async def process_whatsapp_number(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    data = await state.get_data()
    order_id = data.get("order_id")
    order = await session.get(Order, order_id)
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
    await state.update_data(order_id=order_id, phone=phone)

    product = await session.get(Product, order.product_id)
    product_name = product.name if product else "Produto"
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    image_url = await SettingsService.get(session, "delivery_whatsapp_image_url") or None

    # Template WhatsApp (sem credenciais)
    wa_tpl = await MessageService.get_rendered(
        session,
        "delivery_whatsapp",
        store_name=store,
        product_name=product_name,
        price=f"{order.total_price:.2f}",
        date=order.created_at.strftime("%d/%m/%Y %H:%M:%S"),
        payment_method=order.payment_method.value,
        order_id=order.uuid,
        delivery="",  # ainda não libera
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
    )

    await state.set_state(DeliveryStates.confirm_whatsapp)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Confirmar e liberar acesso",
            callback_data=f"wa_confirm:{order_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Corrigir número",
            callback_data=f"wa_edit_phone:{order_id}",
        )
    )
    builder.row(InlineKeyboardButton(text="❌ Cancelar", callback_data="main_menu"))

    status = "✅ Mensagem enviada no WhatsApp." if sent else (
        "⚠️ Não foi possível enviar pelo Baileys agora "
        "(verifique URL/API no admin). Você ainda pode confirmar a liberação aqui."
    )
    await message.answer(
        f"{status}\n\n"
        f"Número: <code>{phone}</code>\n"
        f"Produto: <b>{product_name}</b>\n\n"
        f"No WhatsApp chegou o resumo (sem senha do produto).\n"
        f"Confirme abaixo. Se a verificação estiver ativa, pediremos sua "
        f"<b>senha de liberação</b> (a que você configurou no bot).",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("wa_edit_phone:"))
async def cb_edit_phone(callback: CallbackQuery, state: FSMContext, db_user: User):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(DeliveryStates.waiting_whatsapp)
    await state.update_data(order_id=order_id)
    await callback.message.answer("📲 Digite o número correto (só números, com DDI):")
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

    pwd_enabled = await SettingsService.get_bool(session, "delivery_password_enabled")

    if pwd_enabled:
        await state.set_state(DeliveryStates.waiting_release_password)
        await state.update_data(order_id=order_id)
        await callback.message.answer(
            "🔐 <b>Verificação de liberação</b>\n\n"
            "Digite a <b>senha de liberação</b> configurada no sistema.\n"
            "(É a senha definida pelo admin / pela sua conta de segurança da entrega.)\n\n"
            "Senha errada = os dados do produto <b>não</b> serão enviados no WhatsApp.",
            parse_mode="HTML",
        )
        await callback.answer()
        return

    # Sem senha: libera direto
    ok = await _release_to_whatsapp(session, order)
    await state.clear()
    if ok:
        await callback.message.answer(
            "✅ Acesso enviado no WhatsApp (login e senha do produto).",
            reply_markup=main_menu_kb(),
        )
    else:
        await callback.message.answer(
            "⚠️ Liberado no sistema, mas falha ao enviar no WhatsApp. "
            "Veja os dados no Histórico do bot.",
            reply_markup=main_menu_kb(),
        )
    await callback.answer()


@router.message(DeliveryStates.waiting_release_password)
async def process_release_password(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    data = await state.get_data()
    order_id = data.get("order_id")
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await state.clear()
        await message.answer("❌ Pedido não encontrado.")
        return

    typed = (message.text or "").strip()
    expected = await SettingsService.get(session, "delivery_password")

    # Se o usuário tiver senha própria de saque no futuro, pode combinar;
    # por enquanto usa a senha global de liberação do admin.
    if typed != expected:
        await message.answer(
            "❌ Senha incorreta. Os dados do produto <b>não</b> foram enviados.\n"
            "Tente de novo pelo histórico ou peça suporte.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return

    await state.clear()
    ok = await _release_to_whatsapp(session, order)
    if ok:
        await message.answer(
            "✅ Senha correta. Login e senha do produto enviados no seu WhatsApp.",
            reply_markup=main_menu_kb(),
        )
    else:
        # Fallback: mostra no Telegram se Baileys falhar
        await message.answer(
            f"✅ Senha correta.\n\n"
            f"WhatsApp indisponível no momento. Seus dados:\n"
            f"<code>{order.delivery_content or '—'}</code>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )


async def _release_to_whatsapp(session: AsyncSession, order: Order) -> bool:
    product = await session.get(Product, order.product_id)
    product_name = product.name if product else "Produto"
    phone = order.delivery_whatsapp
    if not phone:
        return False
    activation = (
        await MessageService.get_rendered(session, "delivery_activation_help")
    )["content"]
    return await WhatsAppBaileysService.send_credentials(
        session=session,
        phone=phone,
        product_name=product_name,
        delivery_content=order.delivery_content or "—",
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
