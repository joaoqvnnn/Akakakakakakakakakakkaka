from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from services.ai_assistant import AIAssistant
from keyboards.client_dynamic import main_menu_kb, profile_kb
from services.settings_service import SettingsService

router = Router(name="ai_chat")


@router.message(F.text & ~F.text.startswith("/"))
async def ai_or_fallback(message: Message, session: AsyncSession, db_user: User):
    text = (message.text or "").strip()
    if len(text) < 4:
        return
    if text.replace(",", "").replace(".", "").isdigit():
        return
    if "@" in text and "." in text:
        return

    triggers = (
        "historico", "histórico", "compras", "saldo", "afiliado",
        "indicacao", "indicação", "ajuda", "suporte", "pedido", "pdf",
    )
    low = text.lower()
    if not any(t in low for t in triggers) and not low.startswith("ai "):
        return

    intent = await AIAssistant.classify(text)

    if intent == "history":
        body = await AIAssistant.build_history_text(session, db_user)
        await message.answer(body, reply_markup=await profile_kb(session))
        return
    if intent == "balance":
        await message.answer(
            f"Seu saldo e <b>R$ {db_user.balance:.2f}</b>",
            parse_mode="HTML",
            reply_markup=await main_menu_kb(session),
        )
        return
    if intent == "affiliate":
        await message.answer(
            "Abra o menu <b>Afiliados</b> para ver comissao e link.",
            parse_mode="HTML",
            reply_markup=await main_menu_kb(session),
        )
        return
    if intent == "support":
        link = await SettingsService.get(session, "support_link")
        await message.answer(
            f"Suporte: {link or 'configure no admin'}",
            reply_markup=await main_menu_kb(session),
        )
