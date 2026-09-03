from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from services.affiliate import AffiliateService
from services.settings_service import SettingsService
from services.buttons import ButtonService
from keyboards.client_dynamic import main_menu_kb

router = Router(name="points")


@router.callback_query(F.data == "affiliate_convert_points")
async def cb_convert_points(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    min_pts = await SettingsService.get_int(session, "points_min_convert")
    mult = await SettingsService.get(session, "points_multiplier") or "0.01"
    try:
        preview = float(min_pts) * float(str(mult).replace(",", "."))
    except Exception:
        preview = 0.0

    convert = await ButtonService.get(session, "btn_aff_convert")
    back = await ButtonService.get(session, "btn_back")

    text = (
        f"⭐ <b>Converter pontos</b>\n\n"
        f"Seus pontos: <b>{db_user.affiliate_points}</b>\n"
        f"Mínimo para converter: <b>{min_pts}</b>\n"
        f"Multiplicador: <b>{mult}</b>\n\n"
        f"Exemplo: {min_pts} × {mult} = <b>R$ {preview:.2f}</b>"
    )
    b = InlineKeyboardBuilder()
    if db_user.affiliate_points >= min_pts and min_pts > 0:
        b.row(
            InlineKeyboardButton(
                text=f"✅ {convert}",
                callback_data="affiliate_do_convert",
            )
        )
    b.row(InlineKeyboardButton(text=back, callback_data="affiliates"))
    await callback.message.edit_text(
        text, reply_markup=b.as_markup(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "affiliate_do_convert")
async def cb_do_convert(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    try:
        amount = await AffiliateService.convert_points_to_balance(
            session, db_user.id
        )
        await session.refresh(db_user)
        kb = await main_menu_kb(session)
        await callback.message.edit_text(
            f"✅ Convertido! Você recebeu <b>R$ {amount:.2f}</b> no saldo.\n"
            f"💰 Saldo atual: <b>R$ {db_user.balance:.2f}</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )
        await callback.answer()
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
