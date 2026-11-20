from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import UPLOAD_DIR, settings
from app.db import init_db
from app.logging_setup import setup_logging
from app.routers import api, pages

APP_DIR = Path(__file__).resolve().parent

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    logger.info(
        "启动 %s | AI 模式=%s | 模型=%s | 语音=%s | 数据库=%s",
        settings.brand_name,
        "在线" if settings.ai_enabled else "离线演示",
        settings.llm_model if settings.ai_enabled else "-",
        settings.asr_model if settings.ai_enabled else "-",
        settings.database_url,
    )
    if settings.ai_enabled:
        logger.info("已检测到 DASHSCOPE_API_KEY（前缀 %s…），将真实调用阿里云百炼", settings.dashscope_api_key[:6])
    else:
        logger.info("未检测到 DASHSCOPE_API_KEY，润色走本地断句、追问走本地模板")
    init_db()
    yield


app = FastAPI(
    title=f"{settings.brand_name} {settings.brand_en}",
    description="把长辈的口述榨成一本可以传下去的书",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
app.mount("/media", StaticFiles(directory=str(UPLOAD_DIR)), name="media")

app.include_router(pages.router)
app.include_router(api.router)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {
        "ok": True,
        "ai_enabled": settings.ai_enabled,
        "llm_model": settings.llm_model if settings.ai_enabled else "offline",
    }