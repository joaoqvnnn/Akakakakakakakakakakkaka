from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Category, Product, ProductStatus
from keyboards.client import (
    catalog_categories_kb,
    products_list_kb,
    back_kb,
)
from keyboards.client_dynamic import product_detail_kb_dynamic
from services.settings_service import SettingsService
from config import settings

router = Router(name="catalog")

@router.callback_query(F.data == "catalog")
async def cb_catalog(callback: CallbackQuery, session: AsyncSession, db_user: User):
    result = await session.execute(
        select(Category)
       .where(Category.is_active.is_(True))
       .order_by(Category.position, Category.id)
    )
    categories = list(result.scalars().all())

    if not categories:
        result = await session.execute(
            select(Product)
           .where(Product.status == ProductStatus.ACTIVE)
           .order_by(Product.position, Product.name)
        )
        products = list(result.scalars().all())
        store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
        text = (
            f"📱 <b>{store} | Catálogo de Serviços</b>\n"
            f"{'─' * 12}\n\n"
            f"💰 Saldo da Carteira: <b>R$ {db_user.balance:.2f}</b>\n\n"
            f"⬇️ Selecione um produto abaixo:"
        )
        if not products:
            text += "\n\n❌ Nenhum produto disponível no momento."
            await callback.message.edit_text(
                text, reply_markup=back_kb("main_menu"), parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=products_list_kb(products, 0),
                parse_mode="HTML",
            )
        await callback.answer()
        return

    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    text = (
        f"📱 <b>{store} | Catálogo de Serviços</b>\n"
        f"{'─' * 12}\n\n"
        f"💰 Saldo da Carteira: <b>R$ {db_user.balance:.2f}</b>\n\n"
        f"⬇️ Selecione uma categoria abaixo para ver nossos planos:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=catalog_categories_kb(categories),
        parse_mode="HTML",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("category:"))
async def cb_category(callback: CallbackQuery, session: AsyncSession, db_user: User):
    category_id = int(callback.data.split(":")[1])
    cat = await session.get(Category, category_id)

    result = await session.execute(
        select(Product)
       .where(
            Product.category_id == category_id,
            Product.status == ProductStatus.ACTIVE,
        )
       .order_by(Product.position, Product.id)
    )
    products = list(result.scalars().all())

    title = f"{cat.emoji} {cat.name}" if cat else "Categoria"
    if not products:
        text = f"<b>{title}</b>\n\n❌ Nenhum produto disponível."
        await callback.message.edit_text(
            text, reply_markup=back_kb("catalog"), parse_mode="HTML"
        )
    else:
        text = (
            f"<b>{title}</b>\n\n"
            f"💰 Seu saldo: <b>R$ {db_user.balance:.2f}</b>\n\n"
            f"Escolha um produto:"
        )
        await callback.message.edit_text(
            text,
            reply_markup=products_list_kb(products, category_id),
            parse_mode="HTML",
        )
    await callback.answer()

@router.callback_query(F.data.startswith("product:"))
async def cb_product(callback: CallbackQuery, session: AsyncSession, db_user: User):
    product_id = int(callback.data.split(":")[1])
    product = await session.get(Product, product_id)

    if not product or product.status!= ProductStatus.ACTIVE:
        await callback.answer("Produto indisponível.", show_alert=True)
        return

    product.view_count = (product.view_count or 0) + 1
    has_stock = (product.stock_count or 0) > 0
    status_txt = "🟢 DISPONÍVEL AGORA" if has_stock else "🔴 ESGOTADO"

    text = (
        f"🔥 <b>OPORTUNIDADE EXCLUSIVA</b> 🔥\n"
        f"{product.emoji} <b>{product.name}</b>\n\n"
        f"{status_txt}\n"
        f"├ 💵 Preço: <b>R$ {product.price:.2f}</b>\n"
        f"├ 💰 Seu Saldo: <b>R$ {db_user.balance:.2f}</b>\n"
        f"└ 📦 Estoque: <b>{product.stock_count}</b>\n\n"
        f"📝 <b>Descrição:</b>\n"
        f"{product.description or 'Sem descrição.'}\n\n"
        f"📊 <b>Estatísticas em tempo real:</b>\n"
        f"⚡️ Já foram vendidas <b>{product.sold_count}</b> unidades!\n"
        f"👀 Visualizações: <b>{product.view_count}</b>\n\n"
        f"🛡 Garantia: <b>{product.warranty_days} dias</b>\n"
        f"✅ Compra segura. Ao adquirir, concorda com /termos"
    )

    kb = await product_detail_kb_dynamic(session, product_id, has_stock)

    if product.image_file_id:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            product.image_file_id,
            caption=text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    await callback.answer()
