from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Category, Product, ProductStatus
from keyboards.client_dynamic import categories_kb, products_kb, product_detail_kb
from services.messages import MessageService
from services.settings_service import SettingsService
from config import settings

router = Router(name="catalog")


@router.callback_query(F.data == "catalog")
async def cb_catalog(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    tpl = await MessageService.get_rendered(
        session,
        "catalog",
        store_name=store,
        balance=f"{db_user.balance:.2f}",
    )
    result = await session.execute(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.position, Category.id)
    )
    cats = list(result.scalars().all())

    # Se não houver categorias, lista produtos direto
    if not cats:
        result = await session.execute(
            select(Product)
            .where(Product.status == ProductStatus.ACTIVE)
            .order_by(Product.name)
            .limit(40)
        )
        products = list(result.scalars().all())
        kb = await products_kb(session, products, 0)
        await callback.message.edit_text(
            tpl["content"], reply_markup=kb, parse_mode="HTML"
        )
        await callback.answer()
        return

    kb = await categories_kb(session, cats)
    await callback.message.edit_text(
        tpl["content"], reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("category:"))
async def cb_category(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    category_id = int(callback.data.split(":")[1])
    cat = await session.get(Category, category_id)
    result = await session.execute(
        select(Product)
        .where(
            Product.category_id == category_id,
            Product.status == ProductStatus.ACTIVE,
        )
        .order_by(Product.name)
    )
    products = list(result.scalars().all())
    title = f"{cat.emoji} {cat.name}" if cat else "Produtos"
    text = (
        f"📱 <b>{title}</b>\n\n"
        f"💰 Saldo: <b>R$ {db_user.balance:.2f}</b>\n\n"
        f"Selecione um produto:"
    )
    kb = await products_kb(session, products, category_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("product:"))
async def cb_product(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    product_id = int(callback.data.split(":")[1])
    product = await session.get(Product, product_id)
    if not product or product.status != ProductStatus.ACTIVE:
        await callback.answer("Produto indisponível.", show_alert=True)
        return

    text = (
        f"🔥 <b>OPORTUNIDADE EXCLUSIVA</b> 🔥\n"
        f"🚀 {product.emoji} <b>{product.name}</b>\n\n"
        f"🟢 <b>DISPONÍVEL AGORA</b>\n"
        f"├ 💵 Preço: <b>R$ {product.price:.2f}</b>\n"
        f"├ 💰 Seu Saldo: <b>R$ {db_user.balance:.2f}</b>\n"
        f"└ 📦 Estoque: <b>{product.stock_count}</b>\n\n"
        f"📝 <b>Descrição:</b>\n{product.description or '—'}\n\n"
        f"📊 Estatísticas em tempo real:\n"
        f"⚡️ Já foram vendidas <b>{product.sold_count or 0}</b> unidades!\n\n"
        f"🛡 Garantia: <b>{product.warranty_days or 30} dias</b>\n"
        f"✅ Compra segura. Ao adquirir, concorda com /termos"
    )
    kb = await product_detail_kb(session, product.id, product.category_id)

    if product.image_file_id:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                product.image_file_id,
                caption=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            await callback.answer()
            return
        except Exception:
            pass

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
