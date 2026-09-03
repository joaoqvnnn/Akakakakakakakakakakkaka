from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User
from keyboards.client_dynamic import main_menu_kb
from services.messages import MessageService
from services.settings_service import SettingsService

router = Router(name="start")


async def _welcome_text(session: AsyncSession, db_user: User) -> str:
    store = await SettingsService.get(session, "store_name", settings.STORE_NAME)
    tpl = await MessageService.get_rendered(
        session,
        "start",
        store_name=store,
        user_id=db_user.id,
        balance=f"{db_user.balance:.2f}",
    )
    return tpl["content"]


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, db_user: User):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].isdigit():
        ref_id = int(parts[1])
        if ref_id != db_user.id and not db_user.referred_by_id:
            ref = await session.get(User, ref_id)
            if ref:
                db_user.referred_by_id = ref_id
                ref.total_referrals = (ref.total_referrals or 0) + 1

    text = await _welcome_text(session, db_user)
    kb = await main_menu_kb(session)
    img = await SettingsService.get(session, "welcome_image_file_id")
    if img:
        await message.answer_photo(
            img, caption=text, reply_markup=kb, parse_mode="HTML"
        )
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    text = await _welcome_text(session, db_user)
    kb = await main_menu_kb(session)
    try:
        await callback.message.edit_text(
            text, reply_markup=kb, parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=kb, parse_mode="HTML"
        )
    await callback.answer()


@router.message(Command("id"))
async def cmd_id(message: Message, db_user: User):
    await message.answer(
        f"🆔 Seu id é: <code>{db_user.id}</code>", parse_mode="HTML"
    )


@router.message(Command("saldo"))
async def cmd_saldo(message: Message, db_user: User):
    await message.answer(
        f"╭───────────────────╮\n"
        f"💰 Carteira id: {db_user.id}\n"
        f"💸 Saldo: R${db_user.balance:.2f}\n"
        f"╰───────────────────╯"
    )


@router.message(Command("termos"))
async def cmd_termos(message: Message, session: AsyncSession):
    tpl = await MessageService.get_rendered(session, "terms")
    await message.answer(tpl["content"], parse_mode="HTML")
