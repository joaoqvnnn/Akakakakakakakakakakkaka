from typing import List, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from services.buttons import ButtonService


async def main_menu_kb(session: AsyncSession) -> InlineKeyboardMarkup:
    t = await ButtonService.get_many(
        session,
        [
            "btn_buy",
            "btn_profile",
            "btn_recharge",
            "btn_affiliates",
            "btn_ranking",
            "btn_support",
            "btn_about",
            "btn_search",
            "btn_alerts",
            "btn_gift",
        ],
    )
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=t["btn_buy"], callback_data="catalog"))
    b.row(
        InlineKeyboardButton(text=t["btn_profile"], callback_data="profile"),
        InlineKeyboardButton(text=t["btn_recharge"], callback_data="recharge"),
    )
    b.row(
        InlineKeyboardButton(text=t["btn_affiliates"], callback_data="affiliates"),
        InlineKeyboardButton(text=t["btn_ranking"], callback_data="ranking"),
    )
    b.row(
        InlineKeyboardButton(text=t["btn_search"], callback_data="search"),
        InlineKeyboardButton(text=t["btn_alerts"], callback_data="alerts"),
    )
    b.row(
        InlineKeyboardButton(text=t["btn_gift"], callback_data="gift_card"),
        InlineKeyboardButton(text=t["btn_support"], callback_data="support"),
    )
    b.row(InlineKeyboardButton(text=t["btn_about"], callback_data="about"))
    return b.as_markup()


async def categories_kb(session: AsyncSession, categories: list) -> InlineKeyboardMarkup:
    back = await ButtonService.get(session, "btn_back")
    b = InlineKeyboardBuilder()
    for c in categories:
        b.row(
            InlineKeyboardButton(
                text=f"{c.emoji} {c.name}",
                callback_data=f"category:{c.id}",
            )
        )
    b.row(InlineKeyboardButton(text=back, callback_data="main_menu"))
    return b.as_markup()


async def products_kb(session: AsyncSession, products: list, category_id: int) -> InlineKeyboardMarkup:
    back = await ButtonService.get(session, "btn_back")
    b = InlineKeyboardBuilder()
    for p in products:
        b.row(
            InlineKeyboardButton(
                text=f"{p.emoji} {p.name} — R$ {p.price:.2f}",
                callback_data=f"product:{p.id}",
            )
        )
    b.row(InlineKeyboardButton(text=back, callback_data="catalog"))
    return b.as_markup()


async def product_detail_kb(
    session: AsyncSession, product_id: int, category_id: Optional[int] = None
) -> InlineKeyboardMarkup:
    buy = await ButtonService.get(session, "btn_buy_one")
    multi = await ButtonService.get(session, "btn_buy_multi")
    back = await ButtonService.get(session, "btn_back_catalog")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=buy, callback_data=f"buy:{product_id}:1"))
    b.row(InlineKeyboardButton(text=multi, callback_data=f"buy_multi:{product_id}"))
    back_data = f"category:{category_id}" if category_id else "catalog"
    b.row(InlineKeyboardButton(text=back, callback_data=back_data))
    return b.as_markup()


async def confirm_purchase_kb(
    session: AsyncSession, product_id: int, quantity: int
) -> InlineKeyboardMarkup:
    ok = await ButtonService.get(session, "btn_confirm_buy")
    cancel = await ButtonService.get(session, "btn_cancel_buy")
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=ok, callback_data=f"confirm_buy:{product_id}:{quantity}"
        )
    )
    b.row(
        InlineKeyboardButton(
            text=cancel, callback_data=f"product:{product_id}"
        )
    )
    return b.as_markup()


async def insufficient_balance_kb(
    session: AsyncSession, product_id: int, missing: float, quantity: int = 1
) -> InlineKeyboardMarkup:
    pix = await ButtonService.get(
        session, "btn_generate_pix", amount=f"{missing:.2f}"
    )
    cancel = await ButtonService.get(session, "btn_cancel_product")
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=pix,
            callback_data=f"pix_for_product:{product_id}:{quantity}:{missing:.2f}",
        )
    )
    b.row(InlineKeyboardButton(text=cancel, callback_data="main_menu"))
    return b.as_markup()


async def quantity_cancel_kb(session: AsyncSession) -> InlineKeyboardMarkup:
    cancel = await ButtonService.get(session, "btn_cancel_buy")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=cancel, callback_data="catalog"))
    return b.as_markup()


async def pix_created_kb(session: AsyncSession, payment_uuid: str) -> InlineKeyboardMarkup:
    wait = await ButtonService.get(session, "btn_waiting_payment")
    copy = await ButtonService.get(session, "btn_copy_pix")
    back = await ButtonService.get(session, "btn_back_main")
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=wait, callback_data=f"check_pix:{payment_uuid}"
        )
    )
    b.row(
        InlineKeyboardButton(
            text=copy, callback_data=f"copy_pix:{payment_uuid}"
        )
    )
    b.row(InlineKeyboardButton(text=back, callback_data="main_menu"))
    return b.as_markup()


async def recharge_kb(session: AsyncSession) -> InlineKeyboardMarkup:
    pix = await ButtonService.get(session, "btn_pix_fast")
    back = await ButtonService.get(session, "btn_back")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=pix, callback_data="pix_custom"))
    b.row(InlineKeyboardButton(text=back, callback_data="main_menu"))
    return b.as_markup()


async def profile_kb(session: AsyncSession) -> InlineKeyboardMarkup:
    t = await ButtonService.get_many(
        session,
        ["btn_history", "btn_gift_redeem", "btn_edit_data", "btn_back"],
    )
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=t["btn_history"], callback_data="history"))
    b.row(InlineKeyboardButton(text=t["btn_gift_redeem"], callback_data="gift_card"))
    b.row(InlineKeyboardButton(text=t["btn_edit_data"], callback_data="edit_profile"))
    b.row(InlineKeyboardButton(text=t["btn_back"], callback_data="main_menu"))
    return b.as_markup()


async def order_history_kb(
    session: AsyncSession,
    page: int,
    total: int,
    order_id: int,
    only_active: bool,
) -> InlineKeyboardMarkup:
    t = await ButtonService.get_many(
        session,
        [
            "btn_order_email",
            "btn_order_whatsapp",
            "btn_order_telegram",
            "btn_order_pdf",
            "btn_history_prev",
            "btn_history_next",
            "btn_history_all",
            "btn_back",
        ],
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=t["btn_order_email"], callback_data=f"order_email:{order_id}"),
        InlineKeyboardButton(
            text=t["btn_order_whatsapp"], callback_data=f"order_whatsapp:{order_id}"
        ),
    )
    b.row(
        InlineKeyboardButton(
            text=t["btn_order_telegram"], callback_data=f"order_show:{order_id}"
        ),
        InlineKeyboardButton(text=t["btn_order_pdf"], callback_data=f"order_pdf:{order_id}"),
    )
    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text=t["btn_history_prev"],
                callback_data=f"history_page:{page-1}",
            )
        )
    if page < total:
        nav.append(
            InlineKeyboardButton(
                text=t["btn_history_next"],
                callback_data=f"history_page:{page+1}",
            )
        )
    if nav:
        b.row(*nav)
    if only_active:
        b.row(
            InlineKeyboardButton(
                text=t["btn_history_all"], callback_data="history_all"
            )
        )
    b.row(InlineKeyboardButton(text=t["btn_back"], callback_data="profile"))
    return b.as_markup()


async def gift_card_kb(session: AsyncSession) -> InlineKeyboardMarkup:
    cancel = await ButtonService.get(session, "btn_cancel_buy")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=cancel, callback_data="profile"))
    return b.as_markup()


async def edit_profile_kb(
    session: AsyncSession, whatsapp: Optional[str] = None
) -> InlineKeyboardMarkup:
    wa = await ButtonService.get(session, "btn_edit_whatsapp")
    em = await ButtonService.get(session, "btn_edit_email")
    back = await ButtonService.get(session, "btn_back")
    if whatsapp:
        wa = f"{wa}: {whatsapp}"
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=wa, callback_data="edit_whatsapp"))
    b.row(InlineKeyboardButton(text=em, callback_data="edit_email"))
    b.row(InlineKeyboardButton(text=back, callback_data="profile"))
    return b.as_markup()


async def affiliates_kb(session: AsyncSession, can_withdraw: bool) -> InlineKeyboardMarkup:
    t = await ButtonService.get_many(
        session,
        [
            "btn_aff_withdraw",
            "btn_aff_history",
            "btn_aff_link",
            "btn_aff_convert",
            "btn_back",
        ],
    )
    b = InlineKeyboardBuilder()
    if can_withdraw:
        b.row(
            InlineKeyboardButton(
                text=t["btn_aff_withdraw"], callback_data="affiliate_withdraw"
            )
        )
    b.row(
        InlineKeyboardButton(text=t["btn_aff_convert"], callback_data="affiliate_convert_points")
    )
    b.row(
        InlineKeyboardButton(text=t["btn_aff_history"], callback_data="affiliate_history")
    )
    b.row(InlineKeyboardButton(text=t["btn_aff_link"], callback_data="affiliate_copy_link"))
    b.row(InlineKeyboardButton(text=t["btn_back"], callback_data="main_menu"))
    return b.as_markup()


async def ranking_kb(session: AsyncSession, active: str = "products") -> InlineKeyboardMarkup:
    t = await ButtonService.get_many(
        session,
        [
            "btn_rank_products",
            "btn_rank_recharges",
            "btn_rank_balance",
            "btn_rank_purchases",
            "btn_back",
        ],
    )

    def mark(key: str, name: str) -> str:
        return f"✅ {t[key]}" if active == name else f"☑️ {t[key]}"

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=mark("btn_rank_products", "products"),
            callback_data="ranking:products",
        ),
        InlineKeyboardButton(
            text=mark("btn_rank_recharges", "recharges"),
            callback_data="ranking:recharges",
        ),
    )
    b.row(
        InlineKeyboardButton(
            text=mark("btn_rank_balance", "balance"),
            callback_data="ranking:balance",
        ),
        InlineKeyboardButton(
            text=mark("btn_rank_purchases", "purchases"),
            callback_data="ranking:purchases",
        ),
    )
    b.row(InlineKeyboardButton(text=t["btn_back"], callback_data="main_menu"))
    return b.as_markup()


async def alerts_list_kb(
    session: AsyncSession, products: list, active_map: dict
) -> InlineKeyboardMarkup:
    on = await ButtonService.get(session, "btn_alert_on")
    off = await ButtonService.get(session, "btn_alert_off")
    back = await ButtonService.get(session, "btn_back")
    b = InlineKeyboardBuilder()
    for p in products:
        icon = on if active_map.get(p.id) else off
        b.row(
            InlineKeyboardButton(
                text=f"{icon} {p.name}",
                callback_data=f"alert_toggle:{p.id}",
            )
        )
    b.row(InlineKeyboardButton(text=back, callback_data="main_menu"))
    return b.as_markup()


async def support_kb(session: AsyncSession, link: str) -> InlineKeyboardMarkup:
    support = await ButtonService.get(session, "btn_support")
    back = await ButtonService.get(session, "btn_back")
    b = InlineKeyboardBuilder()
    if link:
        b.row(InlineKeyboardButton(text=support, url=link))
    b.row(InlineKeyboardButton(text=back, callback_data="main_menu"))
    return b.as_markup()


async def delivery_after_buy_kb(session: AsyncSession, order_id: int) -> InlineKeyboardMarkup:
    t = await ButtonService.get_many(
        session, ["btn_order_email", "btn_order_whatsapp", "btn_back_main"]
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=t["btn_order_email"], callback_data=f"order_email:{order_id}"
        ),
        InlineKeyboardButton(
            text=t["btn_order_whatsapp"], callback_data=f"order_whatsapp:{order_id}"
        ),
    )
    b.row(InlineKeyboardButton(text=t["btn_back_main"], callback_data="main_menu"))
    return b.as_markup()


async def back_kb(session: AsyncSession, callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    text = await ButtonService.get(session, "btn_back")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=text, callback_data=callback_data))
    return b.as_markup()
