from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚙️ CONFIGURAÇÕES", callback_data="admin:cfg"))
    builder.row(InlineKeyboardButton(text="🛠 AÇÕES", callback_data="admin:actions"))
    builder.row(InlineKeyboardButton(text="💳 TRANSAÇÕES", callback_data="admin:transactions"))
    builder.row(InlineKeyboardButton(text="🔄 ATUALIZAÇÕES", callback_data="admin:updates"))
    builder.row(InlineKeyboardButton(text="📊 Dashboard", callback_data="admin:dashboard"))
    builder.row(InlineKeyboardButton(text="🔙 Sair", callback_data="main_menu"))
    return builder.as_markup()

def admin_config_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚙️ Configurações Gerais", callback_data="admin:cfg_general")
    )
    builder.row(
        InlineKeyboardButton(text="👑 Configurar Admins", callback_data="admin:cfg_admins")
    )
    builder.row(
        InlineKeyboardButton(text="🤝 Configurar Afiliados", callback_data="admin:cfg_affiliate")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Configurar Usuários", callback_data="admin:cfg_users")
    )
    builder.row(
        InlineKeyboardButton(text="💠 Configurar PIX", callback_data="admin:cfg_pix")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Configurar Logins", callback_data="admin:cfg_logins")
    )
    builder.row(
        InlineKeyboardButton(
            text="📲 Entrega WhatsApp (Baileys)", callback_data="admin:cfg_delivery"
        )
    )
    builder.row(
        InlineKeyboardButton(text="📧 E-mail SMTP", callback_data="admin:cfg_smtp")
    )
    builder.row(
        InlineKeyboardButton(text="🎨 Mensagens", callback_data="admin:messages")
    )
    builder.row(
        InlineKeyboardButton(text="🔘 Editor de Botões", callback_data="admin:buttons")
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Imagens de Produtos", callback_data="admin:product_images")
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Imagem do /start", callback_data="admin:welcome_image")
    )
    builder.row(
        InlineKeyboardButton(text="🔎 Configurar Pesquisa", callback_data="admin:cfg_search")
    )
    builder.row(
        InlineKeyboardButton(text="🔐 Senha do site de saque", callback_data="admin:web_password")
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:main"))
    return builder.as_markup()

def admin_cfg_general_kb(maintenance_on: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    maint = "ON ✅" if maintenance_on else "OFF ❌"
    builder.row(InlineKeyboardButton(text="🔗 Mudar Suporte", callback_data="admin:set_support"))
    builder.row(InlineKeyboardButton(text="📌 Mudar Separador", callback_data="admin:set_separator"))
    builder.row(InlineKeyboardButton(text="📨 Mudar Destino Log", callback_data="admin:set_logs_chat"))
    builder.row(
        InlineKeyboardButton(
            text=f"🔧 Manutenção ({maint})", callback_data="admin:toggle_maintenance"
        )
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    return builder.as_markup()

def admin_cfg_admins_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Adicionar ADM", callback_data="admin:adm_add"))
    builder.row(InlineKeyboardButton(text="➖ Remover ADM", callback_data="admin:adm_remove"))
    builder.row(InlineKeyboardButton(text="📋 Lista de ADM", callback_data="admin:adm_list"))
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    return builder.as_markup()

def admin_cfg_affiliate_kb(enabled: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status = "ON 🟢" if enabled else "OFF 🔴"
    builder.row(
        InlineKeyboardButton(
            text=f"Sistema de Indicação ({status})", callback_data="admin:aff_toggle"
        )
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Pontos por Recarga", callback_data="admin:aff_points_recharge")
    )
    builder.row(
        InlineKeyboardButton(text="📉 Pontos Mín. Converter", callback_data="admin:aff_points_min")
    )
    builder.row(
        InlineKeyboardButton(text="✖️ Multiplicador", callback_data="admin:aff_multiplier")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Comissão %", callback_data="admin:aff_commission")
    )
    builder.row(
        InlineKeyboardButton(text="💸 Saque mínimo", callback_data="admin:aff_min_withdraw")
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    return builder.as_markup()

def admin_cfg_users_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Transmitir a Todos", callback_data="admin:broadcast:all")
    )
    builder.row(
        InlineKeyboardButton(text="🔎 Pesquisar Usuário", callback_data="admin:user_search")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Bônus de Registro", callback_data="admin:set_reg_bonus")
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    return builder.as_markup()

def admin_cfg_pix_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔑 Mudar Token MP", callback_data="admin:pix_token"))
    builder.row(InlineKeyboardButton(text="⬇️ Depósito Mín", callback_data="admin:pix_min"))
    builder.row(InlineKeyboardButton(text="⬆️ Depósito Máx", callback_data="admin:pix_max"))
    builder.row(InlineKeyboardButton(text="⏱ Tempo Expiração", callback_data="admin:pix_exp"))
    builder.row(InlineKeyboardButton(text="🎁 Mudar Bônus %", callback_data="admin:pix_bonus"))
    builder.row(InlineKeyboardButton(text="📌 Mín para Bônus", callback_data="admin:pix_bonus_min"))
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    return builder.as_markup()

def admin_cfg_logins_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Adicionar Login", callback_data="admin:login_add"))
    builder.row(InlineKeyboardButton(text="➖ Remover Login", callback_data="admin:login_remove"))
    builder.row(
        InlineKeyboardButton(
            text="🗑 Remover por Plataforma", callback_data="admin:login_remove_platform"
        )
    )
    builder.row(InlineKeyboardButton(text="📋 Estoque Detalhado", callback_data="admin:stock_view"))
    builder.row(InlineKeyboardButton(text="⚠️ Zerar Estoque", callback_data="admin:stock_clear"))
    builder.row(
        InlineKeyboardButton(text="💰 Mudar Valor Serviço", callback_data="admin:login_price")
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Mudar Valor de Todos", callback_data="admin:login_price_all")
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg"))
    return builder.as_markup()

def admin_user_actions_kb(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="💰 + Saldo", callback_data=f"admin:user_add_balance:{user_id}"
        ),
        InlineKeyboardButton(
            text="💸 - Saldo", callback_data=f"admin:user_remove_balance:{user_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(text="🛑 Bloquear", callback_data=f"admin:user_block:{user_id}"),
        InlineKeyboardButton(text="📊 Histórico", callback_data=f"admin:user_history:{user_id}"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:cfg_users"))
    return builder.as_markup()

def admin_payments_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🟢 Aprovados", callback_data="admin:payments:approved"),
        InlineKeyboardButton(text="🟡 Pendentes", callback_data="admin:payments:pending"),
    )
    builder.row(
        InlineKeyboardButton(text="🔴 Expirados", callback_data="admin:payments:expired"),
        InlineKeyboardButton(text="⚠️ Cancelados", callback_data="admin:payments:cancelled"),
    )
    builder.row(
        InlineKeyboardButton(text="💸 Saques afiliados", callback_data="admin:withdraws")
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:transactions"))
    return builder.as_markup()

def admin_giftcards_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Criar Gift Card", callback_data="admin:gift_create")
    )
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data="admin:actions"))
    return builder.as_markup()

def admin_back_kb(callback_data: str = "admin:main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Voltar", callback_data=callback_data))
    return builder.as_markup()
