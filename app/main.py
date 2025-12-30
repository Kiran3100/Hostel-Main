from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.config.settings import settings
from app.core.middleware import register_middlewares
from app.db.init_db import init_db


def create_app() -> FastAPI:
    """
    Application factory for the FastAPI app.

    - Configures title, version, debug mode from Settings.
    - Registers CORS, core middleware, and exception handlers.
    - Includes the versioned API router under /api/v1.
    """
    app = FastAPI(
        title=settings.APP_NAME,  # Changed from PROJECT_NAME
        debug=settings.DEBUG,
        version=settings.API_VERSION,  # Changed from PROJECT_VERSION
        docs_url="/docs",                              
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS Configuration
    if settings.CORS_ORIGINS and settings.CORS_ORIGINS != ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,  # Default to True for development
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Permissive for development; tighten in production
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Register shared core middlewares (request ID, timing, etc.)
    register_middlewares(app)

    # Mount API v1 under /api/v1
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    # Optional: initialize DB schema in dev (for production, use Alembic)
    @app.on_event("startup")
    async def on_startup() -> None:
        if settings.ENVIRONMENT != "production":
            # For dev/demo only
            init_db()

    return app


app = create_app()