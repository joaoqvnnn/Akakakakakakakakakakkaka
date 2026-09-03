from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SystemSetting


# Textos padrão dos botões (admin pode sobrescrever no banco)
DEFAULT_BUTTONS: Dict[str, str] = {
    "btn_buy_products": "🛍 Comprar Produtos",
    "btn_recharge": "💰 Recarregar Saldo",
    "btn_profile": "👤 Meu Perfil",
    "btn_affiliates": "🤝 Afiliados",
    "btn_ranking": "🏆 Ranking",
    "btn_gift": "🎁 Gift Card",
    "btn_search": "🔎 Pesquisar",
    "btn_alerts": "📢 Alertas",
    "btn_support": "🎧 Atendimento",
    "btn_about": "ℹ️ Sobre o Bot",
    "btn_back": "⏮️ Voltar",
    "btn_back_menu": "🏠 Menu",
    "btn_buy": "💳 Comprar",
    "btn_buy_multi": "🛒 Comprar mais de um",
    "btn_confirm_buy": "✅ Confirmar Compra",
    "btn_cancel": "❌ Cancelar",
    "btn_generate_pix": "💠 Gerar PIX",
    "btn_pix_fast": "💠 Pix Rápido",
    "btn_waiting_pay": "⏳ Aguardando pagamento",
    "btn_history": "🧾 Histórico de Compras",
    "btn_edit_data": "✏️ Alterar Dados",
    "btn_withdraw": "💸 Solicitar Saque",
    "btn_withdraw_history": "📊 Histórico de Saques",
    "btn_my_link": "🔗 Meu Link",
    "btn_email": "📧 Receber por E-mail",
    "btn_whatsapp": "📲 Receber por WhatsApp",
    "btn_alert_on": "📢 Ativar Alerta",
    "btn_out_of_stock": "❌ Sem estoque",
    "btn_security_pwd": "🔐 Senha de saque",
}


class ButtonService:
    PREFIX = "btn_label:"

    @staticmethod
    async def get_label(session: AsyncSession, key: str) -> str:
        if not key.startswith("btn_"):
            key = f"btn_{key}" if not key.startswith("btn_") else key
        db_key = f"{ButtonService.PREFIX}{key}"
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == db_key)
        )
        row = result.scalar_one_or_none()
        if row and row.value:
            return row.value
        return DEFAULT_BUTTONS.get(key, key)

    @staticmethod
    async def set_label(
        session: AsyncSession,
        key: str,
        label: str,
        admin_id: Optional[int] = None,
    ) -> None:
        if not key.startswith("btn_"):
            key = f"btn_{key}"
        db_key = f"{ButtonService.PREFIX}{key}"
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == db_key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = label
            row.updated_by = admin_id
        else:
            session.add(
                SystemSetting(
                    key=db_key,
                    value=label,
                    value_type="string",
                    description=f"Label botão {key}",
                    updated_by=admin_id,
                )
            )
        await session.flush()

    @staticmethod
    async def list_all(session: AsyncSession) -> List[Dict[str, Any]]:
        items = []
        for key, default in DEFAULT_BUTTONS.items():
            label = await ButtonService.get_label(session, key)
            items.append(
                {
                    "key": key,
                    "label": label,
                    "is_custom": label != default,
                    "default": default,
                }
            )
        return items

    @staticmethod
    async def reset_label(session: AsyncSession, key: str) -> None:
        if not key.startswith("btn_"):
            key = f"btn_{key}"
        db_key = f"{ButtonService.PREFIX}{key}"
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == db_key)
        )
        row = result.scalar_one_or_none()
        if row:
            await session.delete(row)
            await session.flush()
