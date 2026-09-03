from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BOT_TOKEN: str
    BOT_USERNAME: str = "larizinhastorebot"
    ADMIN_IDS: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/larizinha"

    MP_ACCESS_TOKEN: str = ""
    STORE_NAME: str = "Larizinha Store"
    SUPPORT_LINK: str = "https://t.me/suporte"

    WEBHOOK_HOST: str = "0.0.0.0"
    WEBHOOK_PORT: int = 8080
    WEBHOOK_PATH: str = "/mercadopago"

    WITHDRAW_WEB_BASE_URL: str = "http://127.0.0.1:8080"
    WITHDRAW_WEB_SECRET: str = "mude-esta-chave-secreta"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    @property
    def admin_ids_list(self) -> List[int]:
        ids = []
        for part in self.ADMIN_IDS.split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    # alias usado no código
    @property
    def ADMIN_IDS_PARSED(self) -> List[int]:
        return self.admin_ids_list


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# compat
if not hasattr(settings, "ADMIN_IDS") or isinstance(settings.ADMIN_IDS, str):
    class _Compat:
        pass
    # handlers usam settings.ADMIN_IDS como lista em vários pontos:
settings.ADMIN_IDS = settings.admin_ids_list  # type: ignore
