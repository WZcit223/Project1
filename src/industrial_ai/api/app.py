"""FastAPI application factory for the Application API (docs/application-api.md).

Routers stay thin: they validate requests, call the application layer and map results to
response models. No algorithm or data logic lives in this package.
"""

from fastapi import FastAPI

from industrial_ai import __version__
from industrial_ai.api.health import router as health_router
from industrial_ai.core.config import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API application. ``settings`` defaults to :func:`load_settings`."""
    app = FastAPI(
        title="Industrial AI Framework — Application API",
        version=__version__,
        description="Prototype API: synthetic data, simulation and scenario analysis.",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.settings = settings if settings is not None else load_settings()
    app.include_router(health_router)
    return app
