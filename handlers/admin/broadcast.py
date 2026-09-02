from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserStatus
from handlers.admin.panel import is_admin
from keyboards.admin import admin_cfg_users_kb, admin_back_kb

router = Router(name="admin_broadcast")


class BroadcastStates(StatesGroup):
    waiting_content = State()


@router.callback_query(F.data == "admin:broadcast:all")
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext, db_user: User):
    if not is_admin(db_user):
        await callback.answer("Acesso negado.", show_alert=True)
        return
    await state.set_state(BroadcastStates.waiting_content)
    await callback.message.edit_text(
        "📢 <b>Transmitir a todos</b>\n\n"
        "Envie o texto (ou foto com legenda) que deseja enviar.\n"
        "/cancelar para sair.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(BroadcastStates.waiting_content)
async def process_broadcast(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    if not is_admin(db_user):
        return
    if message.text and message.text.lower() in ("/cancelar", "cancelar"):
        await state.clear()
        await message.answer("❌ Broadcast cancelado.")
        return

    await state.clear()
    result = await session.execute(
        select(User.id).where(User.status == UserStatus.ACTIVE)
    )
    user_ids = list(result.scalars().all())

    ok = 0
    fail = 0
    status_msg = await message.answer(f"📤 Enviando para {len(user_ids)} usuários...")

    for uid in user_ids:
        try:
            if message.photo:
                await message.bot.send_photo(
                    chat_id=uid,
                    photo=message.photo[-1].file_id,
                    caption=message.caption or "",
                    parse_mode="HTML",
                )
            else:
                await message.bot.send_message(
                    chat_id=uid,
                    text=message.text or message.caption or "",
                    parse_mode="HTML",
                )
            ok += 1
        except Exception:
            fail += 1

    await status_msg.edit_text(
        f"✅ Broadcast finalizado.\n\n"
        f"Enviados: <b>{ok}</b>\n"
        f"Falhas: <b>{fail}</b>",
        parse_mode="HTML",
        reply_markup=admin_cfg_users_kb(),
    )
