from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Category
from handlers.admin.panel import is_admin

router = Router(name="admin_categories")


class CatStates(StatesGroup):
    name = State()
    emoji = State()


@router.callback_query(F.data == "admin:categories")
async def cb_categories(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    result = await session.execute(select(Category).order_by(Category.position, Category.id))
    cats = list(result.scalars().all())

    b = InlineKeyboardBuilder()
    for c in cats:
        status = "✅" if c.is_active else "⏸"
        b.row(
            InlineKeyboardButton(
                text=f"{status} {c.emoji} {c.name}",
                callback_data=f"admin:cat_toggle:{c.id}",
            )
        )
    b.row(InlineKeyboardButton(text="➕ Nova categoria", callback_data="admin:cat_add"))
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))

    await callback.message.edit_text(
        "🗂 <b>CATEGORIAS</b>\n\nToque para ativar/desativar.\nUse ➕ para criar.",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:cat_add")
async def cb_cat_add(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    await state.set_state(CatStates.name)
    await callback.message.edit_text("📝 Nome da categoria:\n/cancelar para sair.")
    await callback.answer()


@router.message(CatStates.name)
async def process_name(message: Message, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.")
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ Nome vazio.")
        return
    await state.update_data(name=name)
    await state.set_state(CatStates.emoji)
    await message.answer("😀 Envie o emoji da categoria (ex: 🎮):")


@router.message(CatStates.emoji)
async def process_emoji(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    data = await state.get_data()
    await state.clear()
    emoji = (message.text or "📦").strip()[:8]
    cat = Category(name=data["name"], emoji=emoji, is_active=True, position=0)
    session.add(cat)
    await message.answer(f"✅ Categoria {emoji} <b>{data['name']}</b> criada.", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:cat_toggle:"))
async def cb_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    cid = int(callback.data.split(":")[2])
    cat = await session.get(Category, cid)
    if cat:
        cat.is_active = not cat.is_active
    await cb_categories(callback, session, db_user)
