from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Product, ProductStatus
from handlers.admin.panel import is_admin

router = Router(name="admin_products_media")


class MediaStates(StatesGroup):
    waiting_photo = State()


@router.callback_query(F.data == "admin:product_images")
async def cb_list(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    result = await session.execute(
        select(Product).order_by(Product.name).limit(40)
    )
    products = list(result.scalars().all())
    b = InlineKeyboardBuilder()
    for p in products:
        icon = "🖼" if p.image_file_id else "⚪"
        b.row(
            InlineKeyboardButton(
                text=f"{icon} {p.name}",
                callback_data=f"admin:prod_img:{p.id}",
            )
        )
    b.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    await callback.message.edit_text(
        "🖼 <b>IMAGENS DE PRODUTOS</b>\n\nToque para enviar/remover foto.",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:prod_img:"))
async def cb_one(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    p = await session.get(Product, pid)
    if not p:
        await callback.answer("Produto não encontrado.", show_alert=True)
        return

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="📷 Enviar/trocar foto",
            callback_data=f"admin:prod_img_set:{pid}",
        )
    )
    if p.image_file_id:
        b.row(
            InlineKeyboardButton(
                text="👁 Ver foto",
                callback_data=f"admin:prod_img_view:{pid}",
            )
        )
        b.row(
            InlineKeyboardButton(
                text="🗑 Remover foto",
                callback_data=f"admin:prod_img_del:{pid}",
            )
        )
    b.row(InlineKeyboardButton(text="🔙 Lista", callback_data="admin:product_images"))
    await callback.message.edit_text(
        f"Produto: <b>{p.name}</b>\n"
        f"Imagem: {'sim' if p.image_file_id else 'não'}",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:prod_img_set:"))
async def cb_set(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    await state.set_state(MediaStates.waiting_photo)
    await state.update_data(product_id=pid)
    await callback.message.edit_text("📷 Envie a foto do produto:")
    await callback.answer()


@router.message(MediaStates.waiting_photo)
async def process_photo(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    if not message.photo:
        await message.answer("❌ Envie uma foto.")
        return
    data = await state.get_data()
    await state.clear()
    p = await session.get(Product, data["product_id"])
    if not p:
        await message.answer("❌ Produto não encontrado.")
        return
    p.image_file_id = message.photo[-1].file_id
    await message.answer(f"✅ Foto salva em <b>{p.name}</b>.", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:prod_img_view:"))
async def cb_view(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    p = await session.get(Product, pid)
    if not p or not p.image_file_id:
        await callback.answer("Sem imagem.", show_alert=True)
        return
    await callback.message.answer_photo(p.image_file_id, caption=p.name)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:prod_img_del:"))
async def cb_del(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    p = await session.get(Product, pid)
    if p:
        p.image_file_id = None
    await callback.answer("Removida.")
    callback.data = f"admin:prod_img:{pid}"
    await cb_one(callback, session, db_user)
