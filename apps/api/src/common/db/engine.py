from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config.settings import settings

engine = create_async_engine(settings.supabase_db_url, pool_pre_ping=True)


async def ping_db() -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
