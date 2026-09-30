import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import asyncio
from backend.api.v1.router import api_router
from backend.core.database import SessionLocal, init_db
from backend.services.scheduler_service import SchedulerService
from backend.services.telegram_service import TelegramService
from config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("backend")

settings = get_settings()


async def _background_scheduler_loop():
    """Autonomous background scheduler checking scheduled sets every 10 minutes."""
    logger.info("Background scheduler worker started (interval: 10m).")
    while True:
        try:
            await asyncio.sleep(600)
            db = SessionLocal()
            try:
                res = SchedulerService.dispatch_scheduled_sets(db=db)
                if res.get("dispatched_sets_count", 0) > 0:
                    logger.info(
                        f"Background scheduler dispatched: {res['dispatched_sets_count']} sets, "
                        f"{res['notified_users_count']} users notified."
                    )
            finally:
                db.close()
        except asyncio.CancelledError:
            logger.info("Background scheduler worker cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in background scheduler worker: {e}", exc_info=True)
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing YouTube Analytics Platform (Multi-Tenant, Dokploy)...")
    init_db()
    logger.info("Database schema verified and ready.")

    # Auto-register Telegram webhook if token is configured
    if settings.TELEGRAM_BOT_TOKEN and " " not in settings.TELEGRAM_BOT_TOKEN:
        try:
            bot_info = TelegramService.get_bot_info()
            if bot_info:
                bot_user = bot_info.get("username")
                logger.info(f"Telegram Bot active: @{bot_user}")
                settings.TELEGRAM_BOT_USERNAME = bot_user

            wh_res = TelegramService.register_webhook()
            logger.info(f"Telegram Webhook auto-registration: {wh_res}")
        except Exception as e:
            logger.warning(f"Could not auto-register Telegram webhook on startup: {e}")

    # Start autonomous background scheduler
    scheduler_task = asyncio.create_task(_background_scheduler_loop())

    yield

    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down backend services.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-user YouTube Analytics Platform with BYOK & Dokploy Docker deployment",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
origins = list(settings.CORS_ORIGINS)
dash_url = settings.DASHBOARD_URL.rstrip("/")
if dash_url and dash_url not in origins:
    origins.append(dash_url)
if "http://localhost:8501" not in origins:
    origins.append("http://localhost:8501")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router (supporting both /api/v1 and /api for compatibility)
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": "2.0.0-multiusers",
        "database": "PostgreSQL / SQLite",
        "domains": {
            "web": f"https://{settings.DOKPLOY_WEB_DOMAIN}",
            "api": f"https://{settings.DOKPLOY_API_DOMAIN}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )
