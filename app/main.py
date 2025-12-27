# app/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.config import settings
from app.core1.middleware import register_middlewares
from app.core1 import init_db  # optional: for dev environments


def create_app() -> FastAPI:
    """
    Application factory for the FastAPI app.

    - Configures title, version, debug mode from Settings.
    - Registers CORS, core middleware, and exception handlers.
    - Includes the versioned API router under /api/v1.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        version="1.0.0",
        docs_url="/docs",                              
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS (use BACKEND_CORS_ORIGINS if provided, else allow all for dev)
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # permissive for development; tighten in production
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Register shared core middlewares (request ID, timing, etc.)
    register_middlewares(app)

    # Global exception handlers to map service-layer errors → HTTP response

    # Mount API v1 under /api/v1
    app.include_router(api_v1_router, prefix="/api/v1")

    # Optional: initialize DB schema in dev (for production, use Alembic)
    @app.on_event("startup")
    async def on_startup() -> None:
        if settings.ENVIRONMENT != "production":
            # For dev/demo only
            init_db()

    return app


app = create_app()