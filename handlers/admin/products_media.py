"""
Imagem do produto: opcional.
Admin pode adicionar, trocar ou remover.
Se não tiver imagem, o bot mostra só texto.
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

router = Router(name="admin_products_media")


class MediaStates(StatesGroup):
    choose_product = State()
    waiting_photo = State()


@router.callback_query(F.data == "admin:product_images")
async def cb_product_images(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return

    result = await session.execute(
        select(Product)
        .where(Product.status != ProductStatus.DELETED)
        .order_by(Product.name)
        .limit(40)
    )
    products = list(result.scalars().all())

    builder = InlineKeyboardBuilder()
    for p in products:
        has = "🖼" if p.image_file_id else "⚪"
        builder.row(
            InlineKeyboardButton(
                text=f"{has} {p.emoji} {p.name}",
                callback_data=f"admin:prod_img:{p.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))

    await callback.message.edit_text(
        "🖼 <b>IMAGENS DOS PRODUTOS</b>\n\n"
        "🖼 = tem imagem | ⚪ = sem imagem\n"
        "A imagem é <b>opcional</b>. Se não colocar, só texto.\n"
        "Toque no produto para adicionar/trocar/remover.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:prod_img:"))
async def cb_prod_img(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    product = await session.get(Product, pid)
    if not product:
        await callback.answer("Não encontrado.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📷 Enviar / trocar foto", callback_data=f"admin:prod_img_set:{pid}"
        )
    )
    if product.image_file_id:
        builder.row(
            InlineKeyboardButton(
                text="🗑 Remover foto", callback_data=f"admin:prod_img_del:{pid}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="👁 Ver foto atual", callback_data=f"admin:prod_img_view:{pid}"
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:product_images"))

    await callback.message.edit_text(
        f"<b>{product.emoji} {product.name}</b>\n"
        f"Imagem: {'sim' if product.image_file_id else 'não'}\n\n"
        f"Escolha:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:prod_img_set:"))
async def cb_prod_img_set(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    await state.set_state(MediaStates.waiting_photo)
    await state.update_data(product_id=pid)
    await callback.message.edit_text(
        "📷 Envie a <b>foto</b> do produto agora.\n/cancelar para sair.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(MediaStates.waiting_photo)
async def process_photo(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
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
    product = await session.get(Product, data["product_id"])
    await state.clear()
    if not product:
        await message.answer("❌ Produto não encontrado.")
        return

    product.image_file_id = message.photo[-1].file_id
    await message.answer(f"✅ Foto salva em <b>{product.name}</b>.", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:prod_img_del:"))
async def cb_prod_img_del(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    product = await session.get(Product, pid)
    if product:
        product.image_file_id = None
    await callback.answer("Foto removida.", show_alert=True)
    callback.data = f"admin:prod_img:{pid}"
    await cb_prod_img(callback, session, db_user)


@router.callback_query(F.data.startswith("admin:prod_img_view:"))
async def cb_prod_img_view(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not is_admin(db_user):
        return
    pid = int(callback.data.split(":")[2])
    product = await session.get(Product, pid)
    if not product or not product.image_file_id:
        await callback.answer("Sem foto.", show_alert=True)
        return
    await callback.message.answer_photo(
        product.image_file_id,
        caption=f"{product.emoji} {product.name}",
    )
    await callback.answer()
