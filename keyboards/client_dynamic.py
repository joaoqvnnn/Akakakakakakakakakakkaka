"""
Menu principal e botões principais usando labels do admin (ButtonService).
Use este arquivo no start/menu; o restante pode migrar aos poucos.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from services.buttons import ButtonService


async def main_menu_kb_dynamic(session: AsyncSession) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_buy_products"),
            callback_data="catalog",
        )
    )
    b.row(
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_recharge"),
            callback_data="recharge",
        ),
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_profile"),
            callback_data="profile",
        ),
    )
    b.row(
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_affiliates"),
            callback_data="affiliates",
        ),
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_ranking"),
            callback_data="ranking",
        ),
    )
    b.row(
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_gift"),
            callback_data="gift_card",
        ),
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_search"),
            callback_data="search",
        ),
    )
    b.row(
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_alerts"),
            callback_data="alerts",
        ),
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_support"),
            callback_data="support",
        ),
    )
    b.row(
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_about"),
            callback_data="about",
        )
    )
    return b.as_markup()


async def product_detail_kb_dynamic(
    session: AsyncSession, product_id: int, has_stock: bool = True
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if has_stock:
        b.row(
            InlineKeyboardButton(
                text=await ButtonService.get_label(session, "btn_buy"),
                callback_data=f"buy:{product_id}:1",
            )
        )
        b.row(
            InlineKeyboardButton(
                text=await ButtonService.get_label(session, "btn_buy_multi"),
                callback_data=f"buy_multi:{product_id}",
            )
        )
    else:
        b.row(
            InlineKeyboardButton(
                text=await ButtonService.get_label(session, "btn_out_of_stock"),
                callback_data="noop",
            )
        )
        b.row(
            InlineKeyboardButton(
                text=await ButtonService.get_label(session, "btn_alert_on"),
                callback_data=f"alert_toggle:{product_id}",
            )
        )
    b.row(
        InlineKeyboardButton(
            text=await ButtonService.get_label(session, "btn_back"),
            callback_data="catalog",
        )
    )
    return b.as_markup()
