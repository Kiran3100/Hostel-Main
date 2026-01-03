from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router  # This should now work
from app.config.settings import settings
from app.core.middleware import register_middlewares
from app.db.init_db import init_db

def create_app() -> FastAPI:
    """
    Application factory for the FastAPI app.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        version=settings.API_VERSION,
        docs_url="/docs",                              
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        description="Comprehensive Hostel Management System API"
    )

    # CORS Configuration
    if settings.CORS_ORIGINS and settings.CORS_ORIGINS != ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Register shared core middlewares
    register_middlewares(app)

    # Mount API v1 under the configured prefix
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    # Debug endpoint for the main app
    @app.get("/debug/app-routes")
    async def debug_app_routes():
        """Debug all routes registered in the main app"""
        return {
            "total_routes": len(app.routes),
            "routes": [
                {
                    "path": route.path,
                    "methods": list(route.methods) if hasattr(route, 'methods') else [],
                    "name": getattr(route, 'name', 'unnamed')
                }
                for route in app.routes
            ]
        }

    @app.on_event("startup")
    async def on_startup() -> None:
        if settings.ENVIRONMENT != "production":
            init_db()
        
        # Log router status on startup
        print(f"App started with {len(app.routes)} total routes")
        print(f"API v1 prefix: {settings.API_V1_STR}")

    return app

app = create_app()