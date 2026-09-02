from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Order, OrderStatus
from keyboards.client import main_menu_kb
from services.settings_service import SettingsService

router = Router(name="start")


async def build_start_text(session: AsyncSession, user: User) -> str:
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    return (
        f"🎬 <b>Bem-vindo à {store}!</b> ✨\n"
        f"A sua central de streamings com entrega <b>100% automática</b>.\n\n"
        f"Pagou, recebeu. Sem filas, sem precisar falar com atendente, 24 horas por dia! ⚡️\n\n"
        f"🛡 <b>Segurança e Suporte:</b>\n"
        f"Mais de 12.000 clientes já passaram por aqui.\n"
        f"Participe da nossa comunidade e veja as referências.\n\n"
        f"💠 <b>Seus Dados:</b>\n"
        f"├ 👤 ID: <code>{user.id}</code>\n"
        f"└ 💰 Saldo Atual: <b>R$ {user.balance:.2f}</b>\n\n"
        f"👇 <b>COMO COMEÇAR:</b>\n"
        f"Clique no botão <b>\"🛍 Comprar Produtos\"</b> abaixo para ver nosso catálogo!"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, session: AsyncSession):
    text = await build_start_text(session, db_user)
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, db_user: User, session: AsyncSession):
    text = await build_start_text(session, db_user)
    await callback.message.edit_text(
        text, reply_markup=main_menu_kb(), parse_mode="HTML"
    )
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
    await message.answer(
        f"🆔 Seu id é: <code>{db_user.id}</code>",
        parse_mode="HTML",
    )


@router.message(Command("termos"))
async def cmd_termos(message: Message):
    text = (
        "📜 <b>Termos de Uso</b>\n\n"
        "1. Ao comprar, você concorda com as regras da loja.\n"
        "2. Produtos digitais não possuem reembolso após a entrega.\n"
        "3. Garantia conforme descrito em cada produto.\n"
        "4. É proibido revender ou compartilhar acessos indevidamente.\n"
        "5. Suporte disponível pelo botão Atendimento.\n\n"
        "Em caso de dúvidas, fale com o suporte."
    )
    await message.answer(text, parse_mode="HTML")


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
    await message.answer(
        f"🧾 Você tem <b>{total}</b> compra(s).\n"
        f"Abra <b>👤 Meu Perfil → Histórico</b> no menu.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("alerta"))
async def cmd_alerta(message: Message):
    await message.answer(
        "⚠️ Use o botão <b>📢 Alertas</b> no menu para ativar "
        "notificações de estoque.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("afiliados"))
async def cmd_afiliados(message: Message):
    await message.answer(
        "🤝 Abra <b>Afiliados</b> no menu principal.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("ranking"))
async def cmd_ranking(message: Message):
    await message.answer(
        "🏆 Abra <b>Ranking</b> no menu principal.",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
