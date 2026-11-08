import asyncio
from uvicorn import Config, Server
from fastapi import FastAPI
from app.config.settings import settings
from app.agents import ALL_AGENTS
from app.utils.logger import logger

bot_app = FastAPI(title="Sponsor Finder Bot Health Service", docs_url=None, redoc_url=None)

@bot_app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "sponsor_finder_bot",
        "agents": len(ALL_AGENTS),
        "port": settings.BOT_PORT
    }

@bot_app.get("/metrics")
async def get_metrics():
    return {
        "agents": [a.get_status() for a in ALL_AGENTS]
    }

async def run_bot_http_server():
    config = Config(
        app=bot_app,
        host=settings.HOST,
        port=settings.BOT_PORT,
        log_level="warning"
    )
    server = Server(config)
    logger.info(f"Starting Bot HTTP Health Server on {settings.HOST}:{settings.BOT_PORT}")
    await server.serve()
