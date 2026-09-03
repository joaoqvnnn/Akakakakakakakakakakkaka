from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from services.messages import MessageService, DEFAULT_TEMPLATES

router = Router(name="admin_messages")

PAGE_SIZE = 8


class EditMsg(StatesGroup):
    waiting_content = State()
    waiting_media = State()


def _list_kb(items, page: int):
    total = len(items)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]
    b = InlineKeyboardBuilder()
    for it in chunk:
        src = "DB" if it["source"] == "database" else "DEF"
        b.row(
            InlineKeyboardButton(
                text=f"[{src}] {it['title'][:28]}",
                callback_data=f"admin:msg_view:{it['key']}",
            )
        )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"admin:msg_page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{pages}", callback_data="admin:messages"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"admin:msg_page:{page+1}"))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    return b


@router.callback_query(F.data == "admin:messages")
async def cb_messages(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    items = await MessageService.list_templates(session)
    await callback.message.edit_text(
        "🎨 <b>MENSAGENS EDITÁVEIS</b>\n\nToque para ver/editar:",
        reply_markup=_list_kb(items, 0).as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:msg_page:"))
async def cb_page(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    page = int(callback.data.split(":")[2])
    items = await MessageService.list_templates(session)
    await callback.message.edit_text(
        "🎨 <b>MENSAGENS EDITÁVEIS</b>",
        reply_markup=_list_kb(items, page).as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:msg_view:"))
async def cb_view(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":", 2)[2]
    tpl = await MessageService.get_template(session, key)
    preview = (tpl["content"] or "")[:900]
    text = (
        f"📝 <b>{tpl.get('title') or key}</b>\n"
        f"Key: <code>{key}</code>\n\n"
        f"<code>{preview}</code>"
    )
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✏️ Editar texto", callback_data=f"admin:msg_edit:{key}"))
    b.row(InlineKeyboardButton(text="📷 Mídia (WA/start)", callback_data=f"admin:msg_media:{key}"))
    b.row(InlineKeyboardButton(text="♻️ Reset padrão", callback_data=f"admin:msg_reset:{key}"))
    b.row(InlineKeyboardButton(text="🔙 Lista", callback_data="admin:messages"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:msg_edit:"))
async def cb_edit(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":", 2)[2]
    await state.set_state(EditMsg.waiting_content)
    await state.update_data(msg_key=key)
    await callback.message.edit_text(
        f"✏️ Envie o novo texto do template <code>{key}</code>\n"
        f"Pode usar HTML e variáveis como {{balance}}, {{user_id}}.\n"
        f"/cancelar para sair.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(EditMsg.waiting_content)
async def process_content(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.")
        return
    data = await state.get_data()
    key = data["msg_key"]
    content = message.text or message.caption or ""
    title = DEFAULT_TEMPLATES.get(key, {}).get("title", key)
    await MessageService.save_template(session, key, content, title=title, admin_id=db_user.id)
    await state.clear()
    await message.answer(f"✅ Template <code>{key}</code> salvo.", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:msg_media:"))
async def cb_media(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":", 2)[2]
    await state.set_state(EditMsg.waiting_media)
    await state.update_data(msg_key=key)
    await callback.message.edit_text("📷 Envie a foto para este template:")
    await callback.answer()


@router.message(EditMsg.waiting_media)
async def process_media(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
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
    await message.answer(f"✅ Mídia salva em <code>{key}</code>.", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:msg_reset:"))
async def cb_reset(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":", 2)[2]
    await MessageService.reset_template(session, key)
    await callback.answer("Resetado.", show_alert=True)
    callback.data = f"admin:msg_view:{key}"
    await cb_view(callback, session, db_user)
