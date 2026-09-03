from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Product, ProductStatus
from keyboards.client_dynamic import main_menu_kb, back_kb
from services.buttons import ButtonService
from services.settings_service import SettingsService

router = Router(name="search")


class SearchStates(StatesGroup):
    waiting_query = State()


@router.callback_query(F.data == "search")
async def cb_search(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    await state.set_state(SearchStates.waiting_query)
    kb = await back_kb(session, "main_menu")
    await callback.message.edit_text(
        "🔎 <b>Pesquisar serviço</b>\n\n"
        "Digite o nome do produto (ex: combate, netflix):\n"
        "/cancelar para sair.",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@router.message(SearchStates.waiting_query)
async def process_search(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer(
            "❌ Cancelado.", reply_markup=await main_menu_kb(session)
        )
        return

    q = (message.text or "").strip()
    if len(q) < 2:
        await message.answer("❌ Digite pelo menos 2 caracteres.")
        return

    result = await session.execute(
        select(Product)
        .where(
            Product.status == ProductStatus.ACTIVE,
            func.lower(Product.name).ilike(f"%{q.lower()}%"),
        )
        .order_by(Product.name)
        .limit(15)
    )
    products = list(result.scalars().all())
    await state.clear()

    if not products:
        await message.answer(
            f"❌ Nenhum serviço encontrado para: <b>{q}</b>",
            parse_mode="HTML",
            reply_markup=await main_menu_kb(session),
        )
        return

    if len(products) == 1:
        await _show_product(message, session, products[0])
        return

    buy = await ButtonService.get(session, "btn_buy_one")
    back = await ButtonService.get(session, "btn_back_main")
    b = InlineKeyboardBuilder()
    for p in products:
        b.row(
            InlineKeyboardButton(
                text=f"{p.emoji} {p.name} — R$ {p.price:.2f}",
                callback_data=f"product:{p.id}",
            )
        )
    b.row(InlineKeyboardButton(text=back, callback_data="main_menu"))
    await message.answer(
        f"🔎 Resultados para <b>{q}</b>:",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


async def _show_product(message, session, p: Product):
    buy = await ButtonService.get(session, "btn_buy_one")
    back = await ButtonService.get(session, "btn_back_main")
    text = (
        f"🎯 <b>{p.name}</b>\n"
        f"💲 Valor: <b>R$ {p.price:.2f}</b>\n"
        f"📦 Estoque: <b>{p.stock_count}</b>\n"
        f"📝 {p.description or '—'}\n\n"
        f"Para comprar, use o botão abaixo."
    )
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=buy, callback_data=f"buy:{p.id}:1"))
    b.row(InlineKeyboardButton(text=back, callback_data="main_menu"))

    img = await SettingsService.get(session, f"search_img:{p.id}")
    if img:
        await message.answer_photo(
            img, caption=text, reply_markup=b.as_markup(), parse_mode="HTML"
        )
    elif p.image_file_id:
        await message.answer_photo(
            p.image_file_id,
            caption=text,
            reply_markup=b.as_markup(),
            parse_mode="HTML",
        )
    else:
        await message.answer(text, reply_markup=b.as_markup(), parse_mode="HTML")
