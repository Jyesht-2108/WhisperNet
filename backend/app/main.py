"""
WhisperNet Backend — FastAPI Application Entry Point

Central intelligence middleware for the WhisperNet Chrome Extension.
Orchestrates context fusion, Databricks lore retrieval, spoiler prevention,
persona prompt synthesis, and OpenAI Realtime ephemeral token exchange.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import context, health, realtime, session, websocket
from app.services.session_manager import SessionManager

# ── Configure logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle events."""
    settings = get_settings()

    # Initialize shared session manager
    sm = SessionManager()
    session.session_manager = sm
    await sm.start_cleanup_loop()

    logger.info("=" * 60)
    logger.info("  WhisperNet Backend starting up")
    logger.info("  Environment : %s", settings.APP_ENV)
    logger.info("  Version     : %s", settings.APP_VERSION)
    logger.info("  Mock DB     : %s", settings.USE_MOCK_DATABRICKS)
    logger.info("  CORS Origins: %s", settings.cors_origin_list)
    logger.info("=" * 60)
    yield
    await sm.stop_cleanup_loop()
    logger.info("WhisperNet Backend shutting down.")


# ── Create FastAPI application ──
app = FastAPI(
    title="WhisperNet Backend API",
    description=(
        "Central intelligence middleware for the WhisperNet Chrome Extension. "
        "Provides context fusion, persona prompt generation, spoiler-safe "
        "Databricks lore retrieval, and OpenAI Realtime ephemeral token exchange."
    ),
    version=get_settings().APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ──
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routers ──
app.include_router(health.router)
app.include_router(context.router)
app.include_router(realtime.router)
app.include_router(session.router)
app.include_router(websocket.router)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint — redirects to API docs."""
    return {
        "service": "WhisperNet Backend",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }

