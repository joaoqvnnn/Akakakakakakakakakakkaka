from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import MessageTemplate


DEFAULT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "start": {
        "title": "Boas-vindas /start",
        "content": (
            "🎬 <b>Bem-vindo à {store_name}!</b> ✨\n"
            "A sua central de streamings com entrega <b>100% automática</b>.\n\n"
            "Pagou, recebeu. Sem filas, 24 horas por dia! ⚡️\n\n"
            "🛡 <b>Segurança e Suporte:</b>\n"
            "Mais de 12.000 clientes já passaram por aqui.\n"
            "Participe da nossa comunidade e veja as referências.\n\n"
            "💠 <b>Seus Dados:</b>\n"
            "├ 👤 ID: <code>{user_id}</code>\n"
            "└ 💰 Saldo Atual: <b>R$ {balance}</b>\n\n"
            "👇 <b>COMO COMEÇAR:</b>\n"
            "Clique no botão <b>\"🛍 Comprar Produtos\"</b> abaixo para ver nosso catálogo!"
        ),
    },
    "catalog": {
        "title": "Catálogo",
        "content": (
            "📱 <b>{store_name} | Catálogo de Serviços</b>\n"
            "────────────\n\n"
            "💰 Saldo da Carteira: <b>R$ {balance}</b>\n\n"
            "⬇️ Selecione uma categoria abaixo:"
        ),
    },
    "payment_approved": {
        "title": "Pagamento aprovado",
        "content": (
            "✅ <b>PAGAMENTO APROVADO!</b>\n\n"
            "💰 Valor: <b>R$ {amount}</b>\n"
            "🎁 Bônus: <b>R$ {bonus}</b>\n"
            "💳 Total: <b>R$ {total}</b>"
        ),
    },
    "payment_expired": {
        "title": "PIX expirado",
        "content": (
            "⌛️ <b>PAGAMENTO PIX EXPIRADO</b>\n\n"
            "⚠️ O tempo limite para realizar este pagamento foi excedido.\n\n"
            "🆔 Referência: <code>{payment_id}</code>\n"
            "💸 Valor: <b>R$ {amount}</b>"
        ),
    },
    "pix_not_found": {
        "title": "PIX ainda não reconhecido",
        "content": (
            "⏳ Ainda não reconhecemos o pagamento no sistema.\n\n"
            "Aguarde alguns segundos e toque em <b>Aguardando pagamento</b> de novo.\n"
            "Se já pagou, a confirmação costuma ser automática."
        ),
    },
    "purchase_success": {
        "title": "Compra aprovada (Telegram)",
        "content": (
            "✅ <b>COMPRA APROVADA!</b>\n\n"
            "🎬 Produto: <b>{product_name}</b>\n"
            "💰 Valor: <b>R$ {price}</b>\n"
            "📅 Data: {date}\n"
            "💳 Pagamento: {payment_method}\n\n"
            "📦 Entrega:\n<code>{delivery}</code>"
        ),
    },
    "delivery_email": {
        "title": "Modelo de e-mail da compra",
        "content": (
            "Olá!\n\n"
            "Sua compra na {store_name} foi confirmada.\n\n"
            "Produto: {product_name}\n"
            "Valor: R$ {price}\n"
            "Data/Hora: {date}\n"
            "Pagamento: {payment_method}\n"
            "ID do pedido: {order_id}\n\n"
            "--- SEUS DADOS DE ACESSO ---\n"
            "{delivery}\n"
            "----------------------------\n\n"
            "COMO ATIVAR:\n"
            "{activation_help}\n\n"
            "Suporte: {support_link}\n"
            "Obrigado pela preferência!"
        ),
    },
    "delivery_whatsapp": {
        "title": "Modelo WhatsApp da compra",
        "content": (
            "✅ *Compra confirmada — {store_name}*\n\n"
            "🎬 *{product_name}*\n"
            "💰 Valor: R$ {price}\n"
            "📅 {date}\n"
            "💳 Pagamento: {payment_method}\n"
            "🆔 Pedido: {order_id}\n\n"
            "Volte ao *Telegram* e confirme a entrega para liberar login e senha."
        ),
    },
    "delivery_activation_help": {
        "title": "Texto 'Como ativar' (e-mail)",
        "content": (
            "1. Abra o aplicativo oficial do serviço.\n"
            "2. Entre com o e-mail e a senha enviados.\n"
            "3. Se pedir código, verifique o e-mail da conta.\n"
            "4. Em caso de dúvida, fale com o suporte."
        ),
    },
    "terms": {
        "title": "Termos de uso",
        "content": (
            "📜 <b>Termos de Uso</b>\n\n"
            "1. Ao comprar, você concorda com as regras da loja.\n"
            "2. Produtos digitais não possuem reembolso após a entrega.\n"
            "3. Garantia conforme descrito em cada produto.\n"
            "4. É proibido revender ou compartilhar acessos indevidamente.\n"
            "5. Suporte disponível pelo botão Atendimento."
        ),
    },
    "flood_warning": {
        "title": "Aviso anti-flood",
        "content": (
            "⏳ Você está enviando comandos muito rápido.\n"
            "Aguarde alguns minutos e tente novamente."
        ),
    },
    "insufficient_balance": {
        "title": "Saldo insuficiente",
        "content": (
            "❌ <b>Saldo insuficiente!</b>\n\n"
            "💰 Seu saldo: <b>R$ {balance}</b>\n"
            "💵 Valor do produto: <b>R$ {price}</b>\n"
            "📉 Faltam: <b>R$ {missing}</b>\n\n"
            "💡 Deseja gerar um PIX no valor de <b>R$ {missing}</b> para completar a compra?"
        ),
    },
}


class MessageService:
    @staticmethod
    async def get_template(session: AsyncSession, key: str) -> Dict[str, Any]:
        result = await session.execute(
            select(MessageTemplate).where(
                MessageTemplate.key == key,
                MessageTemplate.is_active.is_(True),
            )
        )
        tpl = result.scalar_one_or_none()
        if tpl:
            return {
                "key": tpl.key,
                "title": tpl.title,
                "content": tpl.content,
                "parse_mode": tpl.parse_mode or "HTML",
                "media_file_id": tpl.media_file_id,
                "buttons": tpl.buttons or [],
            }
        default = DEFAULT_TEMPLATES.get(key, {})
        return {
            "key": key,
            "title": default.get("title", key),
            "content": default.get("content", f"Template '{key}' não configurado."),
            "parse_mode": "HTML",
            "media_file_id": None,
            "buttons": [],
        }

    @staticmethod
    def render(content: str, **kwargs) -> str:
        try:
            return content.format(**kwargs)
        except (KeyError, ValueError):
            return content

    @staticmethod
    async def get_rendered(session: AsyncSession, key: str, **kwargs) -> Dict[str, Any]:
        tpl = await MessageService.get_template(session, key)
        tpl["content"] = MessageService.render(tpl["content"], **kwargs)
        return tpl

    @staticmethod
    async def list_templates(session: AsyncSession) -> List[Dict[str, Any]]:
        result = await session.execute(select(MessageTemplate))
        db_map = {t.key: t for t in result.scalars().all()}
        keys = sorted(set(DEFAULT_TEMPLATES) | set(db_map))
        items = []
        for key in keys:
            if key in db_map:
                t = db_map[key]
                items.append(
                    {
                        "key": key,
                        "title": t.title or key,
                        "source": "database",
                        "is_active": t.is_active,
                    }
                )
            else:
                items.append(
                    {
                        "key": key,
                        "title": DEFAULT_TEMPLATES[key].get("title", key),
                        "source": "default",
                        "is_active": True,
                    }
                )
        return items

    @staticmethod
    async def save_template(
        session: AsyncSession,
        key: str,
        content: str,
        title: Optional[str] = None,
        admin_id: Optional[int] = None,
        media_file_id: Optional[str] = None,
    ) -> MessageTemplate:
        result = await session.execute(
            select(MessageTemplate).where(MessageTemplate.key == key)
        )
        tpl = result.scalar_one_or_none()
        default = DEFAULT_TEMPLATES.get(key, {})
        if tpl:
            tpl.content = content
            if title is not None:
                tpl.title = title
            if media_file_id is not None:
                tpl.media_file_id = media_file_id
            tpl.updated_by = admin_id
        else:
            tpl = MessageTemplate(
                key=key,
                title=title or default.get("title", key),
                content=content,
                parse_mode="HTML",
                media_file_id=media_file_id,
                updated_by=admin_id,
            )
            session.add(tpl)
        await session.flush()
        return tpl

    @staticmethod
    async def reset_template(session: AsyncSession, key: str) -> bool:
        result = await session.execute(
            select(MessageTemplate).where(MessageTemplate.key == key)
        )
        tpl = result.scalar_one_or_none()
        if tpl:
            await session.delete(tpl)
            await session.flush()
            return True
        return False
