import os
import ssl
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from database.models import Base


def _normalize_database_url(url: str) -> str:
    url = (url or "").strip().strip('"').strip("'")
    if not url:
        raise RuntimeError(
            "DATABASE_URL vazia. No Render: Environment -> DATABASE_URL "
            "(postgresql+asyncpg://...)"
        )

    # Render entrega postgresql:// — SQLAlchemy async precisa +asyncpg
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]

    return url


def _need_ssl(url: str) -> bool:
    # Render Postgres costuma exigir SSL na URL externa
    host = urlparse(url).hostname or ""
    if "render.com" in host or "dpg-" in host:
        return True
    if os.getenv("DB_SSL", "").lower() in ("1", "true", "yes"):
        return True
    return False


DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", "")
)

connect_args = {}
if _need_ssl(DATABASE_URL):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ctx

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
