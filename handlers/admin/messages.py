from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User
from handlers.admin.panel import is_admin
from services.messages import MessageService, DEFAULT_TEMPLATES
from keyboards.admin import admin_back_kb

router = Router(name="admin_messages")


class EditMsg(StatesGroup):
    waiting_content = State()
    waiting_media = State()


@router.callback_query(F.data == "admin:messages")
async def cb_messages_menu(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    templates = await MessageService.list_templates(session)
    builder = InlineKeyboardBuilder()
    for tpl in templates:
        icon = "🗄" if tpl["source"] == "database" else "📄"
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {tpl['title']}",
                callback_data=f"admin:msg_view:{tpl['key']}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))

    await callback.message.edit_text(
        "🎨 <b>EDITOR DE MENSAGENS</b>\n\n"
        "📄 = padrão | 🗄 = personalizado no banco\n\n"
        "Inclui modelos de <b>e-mail</b> e <b>WhatsApp</b> da entrega.\n"
        "Variáveis: <code>{product_name}</code> <code>{price}</code> "
        "<code>{date}</code> <code>{delivery}</code> <code>{order_id}</code> "
        "<code>{payment_method}</code> <code>{store_name}</code> "
        "<code>{activation_help}</code> <code>{support_link}</code>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:msg_view:"))
async def cb_msg_view(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":")[2]
    tpl = await MessageService.get_template(session, key)
    preview = MessageService.render(
        tpl["content"],
        store_name=settings.STORE_NAME,
        user_id=db_user.id,
        balance=f"{db_user.balance:.2f}",
        product_name="COMBATE",
        price="6.00",
        amount="6.00",
        bonus="0.00",
        total="6.00",
        date="02/09/2026 15:30:45",
        delivery="email@exemplo.com:senha123",
        payment_method="Saldo",
        order_id="abc-123",
        payment_id="pix-uuid",
        activation_help="1. Abra o app\n2. Entre com login e senha",
        support_link=settings.SUPPORT_LINK,
    )
    if len(preview) > 3000:
        preview = preview[:3000] + "\n..."

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Editar texto", callback_data=f"admin:msg_edit:{key}")
    )
    if key == "delivery_whatsapp":
        builder.row(
            InlineKeyboardButton(
                text="🖼 Definir imagem padrão WA",
                callback_data=f"admin:msg_media:{key}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="↩️ Restaurar padrão", callback_data=f"admin:msg_reset:{key}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:messages"))

    await callback.message.edit_text(
        f"🎨 <b>{tpl.get('title') or key}</b>\n"
        f"🔑 <code>{key}</code>\n\n"
        f"📝 Preview:\n————————\n{preview}\n————————",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:msg_edit:"))
async def cb_msg_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":")[2]
    await state.set_state(EditMsg.waiting_content)
    await state.update_data(msg_key=key)
    await callback.message.edit_text(
        f"✏️ Editando <code>{key}</code>\n\n"
        "Envie o novo texto (HTML permitido).\n"
        "Use variáveis entre chaves, ex: <code>{product_name}</code>\n\n"
        "/cancelar para sair.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(EditMsg.waiting_content)
async def process_msg_edit(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.")
        return
    data = await state.get_data()
    key = data["msg_key"]
    content = message.text or message.caption or ""
    if not content.strip():
        await message.answer("❌ Texto vazio.")
        return
    default = DEFAULT_TEMPLATES.get(key, {})
    await MessageService.save_template(
        session, key, content, title=default.get("title", key), admin_id=db_user.id
    )
    await state.clear()
    await message.answer(f"✅ Mensagem <b>{key}</b> salva.", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:msg_media:"))
async def cb_msg_media(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":")[2]
    await state.set_state(EditMsg.waiting_media)
    await state.update_data(msg_key=key)
    await callback.message.edit_text(
        "🖼 Envie a <b>foto</b> que será usada no WhatsApp junto com o texto da entrega.\n"
        "/cancelar para sair.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(EditMsg.waiting_media)
async def process_msg_media(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.")
        return
    if not message.photo:
        await message.answer("❌ Envie uma foto.")
        return
    data = await state.get_data()
    key = data["msg_key"]
    file_id = message.photo[-1].file_id
    tpl = await MessageService.get_template(session, key)
    await MessageService.save_template(
        session,
        key,
        tpl["content"],
        title=tpl.get("title"),
        admin_id=db_user.id,
        media_file_id=file_id,
    )
    await state.clear()
    await message.answer("✅ Imagem salva para o template WhatsApp.")


@router.callback_query(F.data.startswith("admin:msg_reset:"))
async def cb_msg_reset(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":")[2]
    await MessageService.reset_template(session, key)
    await callback.answer("Restaurado ao padrão.", show_alert=True)
    callback.data = f"admin:msg_view:{key}"
    await cb_msg_view(callback, session, db_user)
