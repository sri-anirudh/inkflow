import structlog
from fastapi import FastAPI

from src.common.db.engine import ping_db
from src.config.settings import settings

app = FastAPI(title="InkFlow API")
logger = structlog.get_logger()


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        await ping_db()
        db_status = "ok"
    except Exception as exc:
        logger.error("health_check_db_failed", error=str(exc))
        db_status = "unreachable"

    return {"status": "ok", "environment": settings.environment, "db": db_status}
