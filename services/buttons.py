from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SystemSetting


# Todas as chaves de botão usadas no painel do cliente
DEFAULT_BUTTONS: Dict[str, str] = {
    # Menu principal
    "btn_buy": "🛍 Comprar Produtos",
    "btn_profile": "👤 Meu Perfil",
    "btn_recharge": "💰 Recarregar Saldo",
    "btn_affiliates": "🤝 Afiliados",
    "btn_ranking": "🏆 Top Compradores",
    "btn_support": "🎧 Atendimento",
    "btn_about": "ℹ️ Sobre o Bot",
    "btn_search": "🔎 Pesquisar Serviço",
    "btn_alerts": "📢 Alertas",
    "btn_gift": "🎁 Gift Card",
    "btn_back_main": "🏠 Menu",
    "btn_back": "⏮️ Voltar",
    # Catálogo / produto
    "btn_buy_one": "💳 Comprar",
    "btn_buy_multi": "🛒 Comprar mais de um",
    "btn_back_catalog": "⏮️ Voltar",
    "btn_confirm_buy": "✅ Confirmar compra",
    "btn_cancel_buy": "❌ Cancelar",
    "btn_generate_pix": "💠 Gerar PIX de R$ {amount}",
    "btn_cancel_product": "❌ Cancelar produto",
    # PIX
    "btn_waiting_payment": "⏳ Aguardando pagamento",
    "btn_copy_pix": "📋 Copiar PIX",
    "btn_pix_fast": "💠 Pix Rápido",
    # Perfil
    "btn_history": "📋 Histórico de compras",
    "btn_history_all": "📋 Ver todas as compras",
    "btn_gift_redeem": "🎁 Resgatar Gift Card",
    "btn_edit_data": "✏️ Alterar dados",
    "btn_edit_whatsapp": "📱 WhatsApp",
    "btn_edit_email": "📧 E-mail",
    "btn_history_prev": "◀️",
    "btn_history_next": "▶️",
    "btn_order_email": "📧 Receber por E-mail",
    "btn_order_whatsapp": "📲 Receber por WhatsApp",
    "btn_order_telegram": "👁 Mostrar no Telegram",
    "btn_order_pdf": "📄 PDF",
    # Afiliados
    "btn_aff_withdraw": "💸 Solicitar Saque",
    "btn_aff_history": "📊 Histórico de Saques",
    "btn_aff_link": "🔗 Meu Link",
    "btn_aff_convert": "⭐ Converter pontos",
    # Ranking
    "btn_rank_products": "🎬 Serviços",
    "btn_rank_recharges": "💰 Recargas",
    "btn_rank_balance": "💎 Saldo",
    "btn_rank_purchases": "🛒 Compras",
    # PIX expirado / extras
    "btn_do_recharge": "💰 Fazer recarga",
    "btn_main_menu": "🏠 Menu principal",
    # Entrega WhatsApp
    "btn_wa_confirm": "✅ Confirmar e liberar",
    "btn_wa_edit_phone": "✏️ Corrigir número",
    # Alertas
    "btn_alert_on": "✅",
    "btn_alert_off": "☑️",
}


class ButtonService:
    PREFIX = "btn_label:"

    @staticmethod
    async def get(session: AsyncSession, key: str, **fmt) -> str:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == f"{ButtonService.PREFIX}{key}")
        )
        row = result.scalar_one_or_none()
        text = row.value if row and row.value else DEFAULT_BUTTONS.get(key, key)
        if fmt:
            try:
                return text.format(**fmt)
            except (KeyError, ValueError):
                return text
        return text

    @staticmethod
    async def get_many(session: AsyncSession, keys: List[str]) -> Dict[str, str]:
        out = {}
        for k in keys:
            out[k] = await ButtonService.get(session, k)
        return out

    @staticmethod
    async def set(
        session: AsyncSession, key: str, value: str, admin_id: Optional[int] = None
    ) -> None:
        full = f"{ButtonService.PREFIX}{key}"
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == full)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
            if hasattr(row, "updated_by"):
                row.updated_by = admin_id
        else:
            session.add(
                SystemSetting(
                    key=full,
                    value=value,
                    description=f"Label botão {key}",
                )
            )
        await session.flush()

    @staticmethod
    async def reset(session: AsyncSession, key: str) -> bool:
        full = f"{ButtonService.PREFIX}{key}"
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == full)
        )
        row = result.scalar_one_or_none()
        if row:
            await session.delete(row)
            await session.flush()
            return True
        return False

    @staticmethod
    async def list_all(session: AsyncSession) -> List[Dict[str, Any]]:
        items = []
        for key, default in sorted(DEFAULT_BUTTONS.items()):
            current = await ButtonService.get(session, key)
            items.append(
                {
                    "key": key,
                    "default": default,
                    "current": current,
                    "custom": current != default,
                }
            )
        return items
