from typing import List, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import Category, Product


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛍 Comprar Produtos", callback_data="catalog"))
    builder.row(
        InlineKeyboardButton(text="💰 Recarregar Saldo", callback_data="recharge"),
        InlineKeyboardButton(text="👤 Meu Perfil", callback_data="profile"),
    )
    builder.row(
        InlineKeyboardButton(text="🤝 Afiliados", callback_data="affiliates"),
        InlineKeyboardButton(text="🏆 Ranking", callback_data="ranking"),
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Gift Card", callback_data="gift_card"),
        InlineKeyboardButton(text="🔎 Pesquisar", callback_data="search"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Alertas", callback_data="alerts"),
        InlineKeyboardButton(text="🎧 Atendimento", callback_data="support"),
    )
    builder.row(InlineKeyboardButton(text="ℹ️ Sobre o Bot", callback_data="about"))
    return builder.as_markup()


def catalog_categories_kb(categories: List[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        if cat.is_active:
            builder.row(
                InlineKeyboardButton(
                    text=f"{cat.emoji} {cat.name}",
                    callback_data=f"category:{cat.id}",
                )
            )
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="main_menu"))
    return builder.as_markup()


def products_list_kb(products: List[Product], category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in products:
        if p.status.value == "active":
            stock = "🟢" if p.stock_count > 0 else "🔴"
            builder.row(
                InlineKeyboardButton(
                    text=f"{p.emoji} {p.name} — R$ {p.price:.2f} {stock}",
                    callback_data=f"product:{p.id}",
                )
            )
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="catalog"))
    return builder.as_markup()


def product_detail_kb(product_id: int, has_stock: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_stock:
        builder.row(
            InlineKeyboardButton(text="💳 Comprar", callback_data=f"buy:{product_id}:1")
        )
        builder.row(
            InlineKeyboardButton(
                text="🛒 Comprar mais de um", callback_data=f"buy_multi:{product_id}"
            )
        )
    else:
        builder.row(InlineKeyboardButton(text="❌ Sem estoque", callback_data="noop"))
        builder.row(
            InlineKeyboardButton(
                text="📢 Ativar Alerta", callback_data=f"alert_toggle:{product_id}"
            )
        )
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="catalog"))
    return builder.as_markup()


def confirm_purchase_kb(product_id: int, quantity: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Confirmar Compra",
            callback_data=f"confirm_buy:{product_id}:{quantity}",
        )
    )
    builder.row(
        InlineKeyboardButton(text="❌ Cancelar", callback_data=f"product:{product_id}")
    )
    return builder.as_markup()


def insufficient_balance_kb(
    product_id: int, missing_amount: float, quantity: int = 1
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"💠 Gerar PIX R$ {missing_amount:.2f}",
            callback_data=f"pix_for_product:{product_id}:{quantity}:{missing_amount:.2f}",
        )
    )
    builder.row(InlineKeyboardButton(text="❌ Cancelar", callback_data="main_menu"))
    return builder.as_markup()


def quantity_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Cancelar", callback_data="catalog"))
    return builder.as_markup()


def recharge_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💠 Pix Rápido", callback_data="pix_custom"))
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="main_menu"))
    return builder.as_markup()


def pix_created_kb(payment_uuid: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⏳ Aguardando pagamento",
            callback_data=f"check_pix:{payment_uuid}",
        )
    )
    builder.row(InlineKeyboardButton(text="⏮️ Menu", callback_data="main_menu"))
    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🧾 Histórico de Compras", callback_data="history")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Resgatar Gift Card", callback_data="gift_card"),
        InlineKeyboardButton(text="✏️ Alterar Dados", callback_data="edit_profile"),
    )
    builder.row(
        InlineKeyboardButton(text="🔐 Senha de saque", callback_data="security_password")
    )
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="main_menu"))
    return builder.as_markup()


def order_history_kb(
    current_page: int,
    total_pages: int,
    order_id: Optional[int] = None,
    only_active: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav = []
    if current_page > 1:
        nav.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"history_page:{current_page - 1}")
        )
    nav.append(
        InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="noop")
    )
    if current_page < total_pages:
        nav.append(
            InlineKeyboardButton(text="➡️", callback_data=f"history_page:{current_page + 1}")
        )
    if nav:
        builder.row(*nav)
    if order_id:
        builder.row(
            InlineKeyboardButton(text="📧 E-mail", callback_data=f"order_email:{order_id}"),
            InlineKeyboardButton(
                text="📲 WhatsApp", callback_data=f"order_whatsapp:{order_id}"
            ),
        )
        builder.row(
            InlineKeyboardButton(text="📄 Comprovante", callback_data=f"order_pdf:{order_id}")
        )
    if only_active:
        builder.row(
            InlineKeyboardButton(text="📋 Ver todas as compras", callback_data="history_all")
        )
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="profile"))
    return builder.as_markup()


def affiliates_kb(can_withdraw: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_withdraw:
        builder.row(
            InlineKeyboardButton(
                text="💸 Solicitar Saque", callback_data="affiliate_withdraw"
            )
        )
    builder.row(
        InlineKeyboardButton(text="📊 Histórico de Saques", callback_data="affiliate_history")
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Meu Link", callback_data="affiliate_copy_link")
    )
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="main_menu"))
    return builder.as_markup()


def ranking_kb(active_tab: str = "products") -> InlineKeyboardMarkup:
    def mark(tab: str, label: str) -> str:
        return f"✅ {label}" if tab == active_tab else f"☑️ {label}"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=mark("products", "Serviços"), callback_data="ranking:products"),
        InlineKeyboardButton(text=mark("recharges", "Recargas"), callback_data="ranking:recharges"),
    )
    builder.row(
        InlineKeyboardButton(text=mark("balance", "Saldo"), callback_data="ranking:balance"),
        InlineKeyboardButton(text=mark("purchases", "Compras"), callback_data="ranking:purchases"),
    )
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="main_menu"))
    return builder.as_markup()


def gift_card_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Cancelar", callback_data="profile"))
    return builder.as_markup()


def edit_profile_kb(whatsapp: Optional[str] = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    w = whatsapp or "não informado"
    builder.row(
        InlineKeyboardButton(text=f"📱 WhatsApp: {w}", callback_data="edit_whatsapp")
    )
    builder.row(InlineKeyboardButton(text="📧 E-mail", callback_data="edit_email"))
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="profile"))
    return builder.as_markup()


def support_kb(support_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    url = support_link
    if url and not url.startswith("http"):
        url = f"https://t.me/{url.lstrip('@')}"
    if url:
        builder.row(InlineKeyboardButton(text="💬 Falar com Suporte", url=url))
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="main_menu"))
    return builder.as_markup()


def back_kb(callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data=callback_data))
    return builder.as_markup()


def alerts_list_kb(products: list, active_map: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in products:
        on = active_map.get(p.id, False)
        status = "✅" if on else "❌"
        stock = f"({p.stock_count})" if p.stock_count else "(0)"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {p.emoji} {p.name} {stock}",
                callback_data=f"alert_toggle:{p.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="⏮️ Voltar", callback_data="main_menu"))
    return builder.as_markup()
