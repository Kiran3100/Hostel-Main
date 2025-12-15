# app/core/middleware.py
from __future__ import annotations

"""
Core FastAPI middleware registration helpers.

This module defines small helpers to register:
- CORS middleware.
- Request ID correlation middleware.
- Simple timing middleware.

These can be composed via `register_middlewares` to keep your app
startup code clean and consistent.
"""

import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.core.constants import HEADER_REQUEST_ID


def register_cors_middleware(app: FastAPI, allow_origins: list[str] | None = None) -> None:
    """
    Register CORS middleware on the given FastAPI app.

    Args:
        app: FastAPI application instance.
        allow_origins: List of origins to allow. Defaults to ["*"] for
                       convenience; this should be tightened in production.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def register_request_id_middleware(app: FastAPI) -> None:
    """
    Register middleware to inject a request ID into the request state
    and response headers for tracing and correlation.

    - If the incoming request already has HEADER_REQUEST_ID, it is reused.
    - Otherwise a new UUID4 is generated.
    """

    @app.middleware("http")
    async def add_request_id_header(request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(HEADER_REQUEST_ID) or str(uuid.uuid4())
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers[HEADER_REQUEST_ID] = request_id
        return response


def register_timing_middleware(app: FastAPI) -> None:
    """
    Register middleware to add an X-Process-Time header with the request
    processing time in seconds (as a float formatted to 4 decimal places).
    """

    @app.middleware("http")
    async def add_timing_header(request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{duration:.4f}"
        return response


def register_middlewares(app: FastAPI) -> None:
    """
    Convenience function to register all core middlewares at once.

    Currently includes:
    - CORS middleware.
    - Request ID middleware.
    - Timing middleware.
    """
    register_cors_middleware(app)
    register_request_id_middleware(app)
    register_timing_middleware(app)