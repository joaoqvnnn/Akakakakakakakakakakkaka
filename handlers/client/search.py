from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Product, ProductStatus
from keyboards.client import back_kb
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

router = Router(name="search")


class SearchStates(StatesGroup):
    waiting_query = State()


@router.callback_query(F.data == "search")
async def cb_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchStates.waiting_query)
    await callback.message.edit_text(
        "🔎 <b>Pesquisar Serviço</b>\n\n"
        "Digite o nome do serviço (ex: combate, netflix, canva).\n\n"
        "💡 /cancelar para sair.",
        reply_markup=back_kb("main_menu"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SearchStates.waiting_query)
async def process_search(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
):
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        from keyboards.client import main_menu_kb

        await message.answer("❌ Pesquisa cancelada.", reply_markup=main_menu_kb())
        return

    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("❌ Digite pelo menos 2 caracteres.")
        return

    await state.clear()

    result = await session.execute(
        select(Product)
        .where(
            Product.status == ProductStatus.ACTIVE,
            or_(
                func.lower(Product.name).contains(query.lower()),
                func.lower(func.coalesce(Product.description, "")).contains(
                    query.lower()
                ),
            ),
        )
        .order_by(Product.sold_count.desc())
        .limit(15)
    )
    products = list(result.scalars().all())

    if not products:
        await message.answer(
            f"❌ Nenhum serviço encontrado para: <b>{query}</b>",
            reply_markup=back_kb("search"),
            parse_mode="HTML",
        )
        return

    builder = InlineKeyboardBuilder()
    lines = [f"🔎 <b>Resultados:</b> <code>{query}</code>\n"]
    for p in products:
        stock = "🟢" if p.stock_count > 0 else "🔴"
        lines.append(f"{p.emoji} <b>{p.name}</b> — R$ {p.price:.2f} {stock}")
        builder.row(
            InlineKeyboardButton(
                text=f"{p.emoji} {p.name} — R$ {p.price:.2f}",
                callback_data=f"product:{p.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔎 Nova pesquisa", callback_data="search"))
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="main_menu"))

    await message.answer(
        "\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML"
    )
