from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from services.buttons import ButtonService, DEFAULT_BUTTONS

router = Router(name="admin_buttons")

PAGE_SIZE = 8


class BtnEdit(StatesGroup):
    waiting = State()


def _list_kb(items, page: int) -> InlineKeyboardBuilder:
    total = len(items)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]

    b = InlineKeyboardBuilder()
    for it in chunk:
        mark = "✏️" if it["custom"] else "▪️"
        label = it["current"][:28]
        b.row(
            InlineKeyboardButton(
                text=f"{mark} {label}",
                callback_data=f"admin:btn_view:{it['key']}",
            )
        )
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin:btn_page:{page-1}")
        )
    nav.append(
        InlineKeyboardButton(text=f"{page+1}/{pages}", callback_data="admin:buttons")
    )
    if page < pages - 1:
        nav.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin:btn_page:{page+1}")
        )
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    return b


@router.callback_query(F.data == "admin:buttons")
async def cb_buttons(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    items = await ButtonService.list_all(session)
    text = (
        "🔘 <b>EDITOR DE BOTÕES</b>\n\n"
        "Toque em um botão para editar o texto.\n"
        "✏️ = personalizado · ▪️ = padrão\n"
        f"Total: <b>{len(items)}</b> labels"
    )
    await callback.message.edit_text(
        text, reply_markup=_list_kb(items, 0).as_markup(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:btn_page:"))
async def cb_page(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    page = int(callback.data.split(":")[2])
    items = await ButtonService.list_all(session)
    await callback.message.edit_text(
        "🔘 <b>EDITOR DE BOTÕES</b>\n\nToque para editar:",
        reply_markup=_list_kb(items, page).as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:btn_view:"))
async def cb_view(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":", 2)[2]
    current = await ButtonService.get(session, key)
    default = DEFAULT_BUTTONS.get(key, key)
    text = (
        f"🔘 <b>{key}</b>\n\n"
        f"Atual:\n<code>{current}</code>\n\n"
        f"Padrão:\n<code>{default}</code>\n\n"
        f"Variáveis possíveis: <code>{{amount}}</code> (PIX)"
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✏️ Editar texto", callback_data=f"admin:btn_edit:{key}")
    )
    b.row(
        InlineKeyboardButton(text="♻️ Resetar padrão", callback_data=f"admin:btn_reset:{key}")
    )
    b.row(InlineKeyboardButton(text="🔙 Lista", callback_data="admin:buttons"))
    await callback.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:btn_edit:"))
async def cb_edit(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":", 2)[2]
    await state.set_state(BtnEdit.waiting)
    await state.update_data(btn_key=key)
    await callback.message.edit_text(
        f"✏️ Envie o novo texto do botão <code>{key}</code>\n"
        f"/cancelar para sair.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(BtnEdit.waiting)
async def process_edit(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.")
        return
    data = await state.get_data()
    key = data.get("btn_key")
    text = (message.text or "").strip()
    if not text or len(text) > 64:
        await message.answer("❌ Texto vazio ou maior que 64 caracteres.")
        return
    await state.clear()
    await ButtonService.set(session, key, text, db_user.id)
    await message.answer(f"✅ Botão <code>{key}</code> atualizado:\n{text}", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:btn_reset:"))
async def cb_reset(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":", 2)[2]
    await ButtonService.reset(session, key)
    await callback.answer("Resetado ao padrão.", show_alert=True)
    # reabre view
    callback.data = f"admin:btn_view:{key}"
    await cb_view(callback, session, db_user)
