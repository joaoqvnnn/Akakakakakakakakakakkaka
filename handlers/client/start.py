from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Order, OrderStatus
from keyboards.client_dynamic import main_menu_kb_dynamic
from services.settings_service import SettingsService
from services.messages import MessageService

router = Router(name="start")


async def build_start_text(session: AsyncSession, user: User) -> str:
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    tpl = await MessageService.get_rendered(
        session,
        "start",
        store_name=store,
        user_id=user.id,
        balance=f"{user.balance:.2f}",
    )
    return tpl["content"]


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, session: AsyncSession):
    text = await build_start_text(session, db_user)
    kb = await main_menu_kb_dynamic(session)

    # Imagem de boas-vindas opcional (file_id salvo em setting welcome_image_file_id)
    welcome_img = await SettingsService.get(session, "welcome_image_file_id")
    if welcome_img:
        await message.answer_photo(
            welcome_img, caption=text, reply_markup=kb, parse_mode="HTML"
        )
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, db_user: User, session: AsyncSession):
    text = await build_start_text(session, db_user)
    kb = await main_menu_kb_dynamic(session)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.message(Command("saldo"))
async def cmd_saldo(message: Message, db_user: User):
    await message.answer(
        f"╭───────────────────╮\n"
        f"💰 Carteira id: <code>{db_user.id}</code>\n"
        f"💸 Saldo: <b>R$ {db_user.balance:.2f}</b>\n"
        f"╰───────────────────╯",
        parse_mode="HTML",
    )


@router.message(Command("id"))
async def cmd_id(message: Message, db_user: User):
    await message.answer(f"🆔 Seu id é: <code>{db_user.id}</code>", parse_mode="HTML")


@router.message(Command("termos"))
async def cmd_termos(message: Message, session: AsyncSession):
    tpl = await MessageService.get_template(session, "terms")
    # se não existir template terms, texto padrão
    content = tpl.get("content") or (
        "📜 <b>Termos de Uso</b>\n\n"
        "1. Ao comprar, concorda com as regras.\n"
        "2. Digital sem reembolso após entrega.\n"
        "3. Garantia conforme o produto.\n"
        "4. Suporte pelo botão Atendimento."
    )
    await message.answer(content, parse_mode="HTML")


@router.message(Command("historico"))
async def cmd_historico(message: Message, session: AsyncSession, db_user: User):
    total = (
        await session.execute(
            select(func.count(Order.id)).where(
                Order.user_id == db_user.id,
                Order.status == OrderStatus.DELIVERED,
            )
        )
    ).scalar_one() or 0
    kb = await main_menu_kb_dynamic(session)
    await message.answer(
        f"🧾 Você tem <b>{total}</b> compra(s).\nAbra <b>Perfil → Histórico</b>.",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.message(Command("alerta"))
async def cmd_alerta(message: Message, session: AsyncSession):
    kb = await main_menu_kb_dynamic(session)
    await message.answer(
        "⚠️ Use <b>Alertas</b> no menu.", parse_mode="HTML", reply_markup=kb
    )


@router.message(Command("afiliados"))
async def cmd_afiliados(message: Message, session: AsyncSession):
    kb = await main_menu_kb_dynamic(session)
    await message.answer(
        "🤝 Abra <b>Afiliados</b> no menu.", parse_mode="HTML", reply_markup=kb
    )


@router.message(Command("ranking"))
async def cmd_ranking(message: Message, session: AsyncSession):
    kb = await main_menu_kb_dynamic(session)
    await message.answer(
        "🏆 Abra <b>Ranking</b> no menu.", parse_mode="HTML", reply_markup=kb
    )


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
