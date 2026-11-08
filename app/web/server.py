from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from uvicorn import Config, Server

from app.config.settings import settings
from app.web.routes.auth_routes import router as auth_router
from app.web.routes.admin_routes import router as admin_router
from app.web.routes.public_routes import router as public_router
from app.web.routes.api_routes import router as api_router
from app.utils.logger import logger

web_app = FastAPI(
    title="Sponsor Finder SaaS Web Platform",
    description="Multi-Agent AI Sponsorship Hunter Web Dashboard",
    version="1.0.0"
)

# Add session middleware for admin dashboard auth
web_app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    max_age=86400 * 7
)

# Register routes
web_app.include_router(public_router)
web_app.include_router(auth_router)
web_app.include_router(admin_router)
web_app.include_router(api_router)

async def run_web_server():
    config = Config(
        app=web_app,
        host=settings.HOST,
        port=settings.WEB_PORT,
        log_level="info"
    )
    server = Server(config)
    logger.info(f"Starting Web SaaS Server on {settings.HOST}:{settings.WEB_PORT}")
    await server.serve()
