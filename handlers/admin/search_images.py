"""
Imagens opcionais para resultado da pesquisa de serviços.
Salva file_id por product_id em settings: search_img:{product_id}
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Product, ProductStatus
from handlers.admin.panel import is_admin
from services.settings_service import SettingsService

router = Router(name="admin_search_images")


class SearchImg(StatesGroup):
    waiting = State()


@router.callback_query(F.data == "admin:cfg_search")
async def cb_cfg_search(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    result = await session.execute(
        select(Product)
        .where(Product.status == ProductStatus.ACTIVE)
        .order_by(Product.name)
        .limit(30)
    )
    products = list(result.scalars().all())
    b = InlineKeyboardBuilder()
    for p in products:
        key = f"search_img:{p.id}"
        has = await SettingsService.get(session, key)
        icon = "🖼" if has else "⚪"
        b.row(
            InlineKeyboardButton(
                text=f"{icon} {p.name}",
                callback_data=f"admin:search_img:{p.id}",
            )
        )
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    await callback.message.edit_text(
        "🔎 <b>IMAGENS DA PESQUISA</b>\n\n"
        "Opcional. Se não colocar, a pesquisa mostra só texto.",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:search_img:"))
async def cb_pick(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    key = f"search_img:{pid}"
    has = await SettingsService.get(session, key)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📷 Enviar foto", callback_data=f"admin:search_img_set:{pid}"))
    if has:
        b.row(InlineKeyboardButton(text="🗑 Remover", callback_data=f"admin:search_img_del:{pid}"))
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg_search"))
    await callback.message.edit_text(
        f"Produto ID <code>{pid}</code>\nImagem: {'sim' if has else 'não'}",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:search_img_set:"))
async def cb_set(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    await state.set_state(SearchImg.waiting)
    await state.update_data(product_id=pid)
    await callback.message.edit_text("📷 Envie a foto:")
    await callback.answer()


@router.message(SearchImg.waiting)
async def process(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    if not message.photo:
        await message.answer("❌ Envie uma foto.")
        return
    data = await state.get_data()
    await state.clear()
    pid = data["product_id"]
    await SettingsService.set(
        session, f"search_img:{pid}", message.photo[-1].file_id, db_user.id
    )
    await message.answer("✅ Imagem de pesquisa salva.")


@router.callback_query(F.data.startswith("admin:search_img_del:"))
async def cb_del(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    await SettingsService.set(session, f"search_img:{pid}", "", db_user.id)
    await callback.answer("Removida.")
    await cb_cfg_search(callback, session, db_user)
