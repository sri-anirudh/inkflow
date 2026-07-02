from fastapi import FastAPI

from src.config.settings import settings

app = FastAPI(title="InkFlow API")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
