from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Bot
    BOT_TOKEN: str
    BOT_USERNAME: str = "larizinhastorebot"

    # Admins (donos no .env; outros admins podem ser adicionados pelo bot)
    ADMIN_IDS: List[int] = Field(default_factory=list)

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [int(x) for x in v]
        return [int(x.strip()) for x in str(v).split(",") if x.strip()]

    # Banco / Redis
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/larizinha"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Mercado Pago
    MP_ACCESS_TOKEN: str = ""
    MP_PUBLIC_KEY: Optional[str] = None
    MP_NOTIFICATION_URL: Optional[str] = None

    # Loja
    STORE_NAME: str = "Larizinha Store"
    STORE_TIMEZONE: str = "America/Sao_Paulo"
    SUPPORT_USERNAME: str = ""
    SUPPORT_LINK: str = "https://t.me/suporte"

    # PIX (padrão; o admin pode sobrescrever no banco depois)
    PIX_EXPIRATION_MINUTES: int = 10
    PIX_MIN_VALUE: float = 4.00
    PIX_MAX_VALUE: float = 5000.00

    # Bônus
    BONUS_ENABLED: bool = True
    BONUS_PERCENT: float = 10.0
    BONUS_MIN_VALUE: float = 10.00

    # Afiliados
    AFFILIATE_ENABLED: bool = True
    AFFILIATE_COMMISSION_PERCENT: float = 20.0
    AFFILIATE_MIN_WITHDRAW: float = 20.00

    # Servidor HTTP (webhook MP + página de saque bancário)
    WEBHOOK_HOST: str = "0.0.0.0"
    WEBHOOK_PORT: int = 8080
    WEBHOOK_PATH: str = "/webhook/mercadopago"

    # Única parte web: formulário de saque
    WITHDRAW_WEB_BASE_URL: str = "http://localhost:8080"
    WITHDRAW_WEB_SECRET: str = "change-me-in-production"

    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
