"""
WhisperNet Backend — Health Check Router

Provides basic health and readiness endpoints for Docker health checks,
load balancers, and team verification.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings
from app.models.responses import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic health check",
    description="Returns server status, version, and timestamp. Used by Docker healthcheck.",
)
async def health_check() -> HealthResponse:
    """Basic liveness probe."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness check",
    description="Validates that the server is ready to handle requests. "
    "In production, this would verify Databricks connectivity.",
)
async def readiness_check() -> HealthResponse:
    """
    Readiness probe — in production, this would test connectivity
    to Databricks and OpenAI. For now, returns healthy if the
    server is up and configuration is loaded.
    """
    settings = get_settings()
    return HealthResponse(
        status="ready",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )
