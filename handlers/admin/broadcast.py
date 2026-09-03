from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.admin.panel import is_admin
from keyboards.admin import admin_cfg_users_kb

router = Router(name="admin_broadcast")


class BroadcastStates(StatesGroup):
    waiting = State()


@router.callback_query(F.data == "admin:broadcast:all")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    await state.set_state(BroadcastStates.waiting)
    await callback.message.edit_text(
        "📢 <b>Transmitir a todos</b>\n\n"
        "Envie o texto ou uma foto com legenda.\n"
        "/cancelar para sair.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(BroadcastStates.waiting)
async def process_broadcast(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Cancelado.", reply_markup=admin_cfg_users_kb())
        return

    await state.clear()
    result = await session.execute(
        select(User.id).where(User.is_blocked.is_(False))
    )
    ids = [row[0] for row in result.all()]

    ok = 0
    fail = 0
    status = await message.answer(f"⏳ Enviando para {len(ids)} usuários...")

    for uid in ids:
        try:
            if message.photo:
                await message.bot.send_photo(
                    uid,
                    message.photo[-1].file_id,
                    caption=message.caption,
                    parse_mode="HTML",
                )
            else:
                await message.bot.send_message(
                    uid,
                    message.text or message.caption or "",
                    parse_mode="HTML",
                )
            ok += 1
        except Exception:
            fail += 1

    await status.edit_text(
        f"✅ Broadcast finalizado.\nEnviados: <b>{ok}</b>\nFalhas: <b>{fail}</b>",
        parse_mode="HTML",
        reply_markup=admin_cfg_users_kb(),
    )
