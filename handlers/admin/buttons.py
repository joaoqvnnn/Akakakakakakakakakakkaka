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


class BtnEdit(StatesGroup):
    waiting_label = State()


@router.callback_query(F.data == "admin:buttons")
async def cb_buttons_menu(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    items = await ButtonService.list_all(session)
    builder = InlineKeyboardBuilder()
    for it in items[:40]:
        mark = "✏️" if it["is_custom"] else "📄"
        builder.row(
            InlineKeyboardButton(
                text=f"{mark} {it['label'][:40]}",
                callback_data=f"admin:btn_edit:{it['key']}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))

    await callback.message.edit_text(
        "🔘 <b>EDITOR DE BOTÕES</b>\n\n"
        "📄 = padrão | ✏️ = personalizado\n"
        "Toque no botão para mudar o texto (emoji permitido).\n"
        "Cor do botão o Telegram <b>não permite</b> alterar.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:btn_edit:"))
async def cb_btn_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":")[2]
    current = await ButtonService.get_label(session, key)
    default = DEFAULT_BUTTONS.get(key, "")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Novo texto", callback_data=f"admin:btn_set:{key}")
    )
    builder.row(
        InlineKeyboardButton(text="↩️ Restaurar padrão", callback_data=f"admin:btn_reset:{key}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:buttons"))

    await callback.message.edit_text(
        f"🔑 <code>{key}</code>\n\n"
        f"Atual: <b>{current}</b>\n"
        f"Padrão: <code>{default}</code>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:btn_set:"))
async def cb_btn_set(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":")[2]
    await state.set_state(BtnEdit.waiting_label)
    await state.update_data(btn_key=key)
    await callback.message.edit_text(
        f"✏️ Envie o novo texto do botão <code>{key}</code>\n"
        f"(pode usar emoji)\n/cancelar para sair.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(BtnEdit.waiting_label)
async def process_btn_label(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.")
        return
    data = await state.get_data()
    key = data["btn_key"]
    label = (message.text or "").strip()
    if not label:
        await message.answer("❌ Texto vazio.")
        return
    await ButtonService.set_label(session, key, label, db_user.id)
    await state.clear()
    await message.answer(f"✅ Botão atualizado:\n<b>{label}</b>", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:btn_reset:"))
async def cb_btn_reset(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    key = callback.data.split(":")[2]
    await ButtonService.reset_label(session, key)
    await callback.answer("Restaurado.", show_alert=True)
    callback.data = f"admin:btn_edit:{key}"
    await cb_btn_edit(callback, None, session, db_user)  # type: ignore
