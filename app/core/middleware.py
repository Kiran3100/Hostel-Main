# app/core/middleware.py
"""
Core middleware registration for the FastAPI application.

This module provides essential middleware components for request tracking,
timing, error handling, and logging.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

try:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a unique request ID to each incoming request.
    
    The request ID is:
    - Stored in request.state.request_id
    - Added to response headers as X-Request-ID
    - Useful for tracking requests across logs and services
    """
    
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if request ID already exists in headers (from upstream proxy/service)
        request_id = request.headers.get(self.header_name)
        
        # If not, generate a new UUID
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Store in request state for access in route handlers
        request.state.request_id = request_id
        
        # Process the request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers[self.header_name] = request_id
        
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that measures and logs request processing time.
    
    Adds X-Process-Time header to responses with the processing duration in seconds.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Add processing time to response headers
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        
        # Get request ID if available
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log request completion with details
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url.path),
                "query_params": str(request.url.query) if request.url.query else None,
                "status_code": response.status_code,
                "process_time": f"{process_time:.4f}s",
                "client_host": request.client.host if request.client else None,
            }
        )
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds common security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs errors and exceptions during request processing.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            
            # Log errors (4xx and 5xx status codes)
            if response.status_code >= 400:
                request_id = getattr(request.state, "request_id", "unknown")
                logger.warning(
                    f"Request returned error status {response.status_code}",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "url": str(request.url.path),
                        "status_code": response.status_code,
                        "client_host": request.client.host if request.client else None,
                    }
                )
            
            return response
            
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                f"Request processing failed: {str(exc)}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url.path),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "client_host": request.client.host if request.client else None,
                },
                exc_info=True
            )
            raise


def register_middlewares(app: FastAPI, include_security: bool = True) -> None:
    """
    Register all core middlewares to the FastAPI application.
    
    Middlewares are registered in reverse order of execution (LIFO).
    The last middleware added is the first one to process the request.
    
    Args:
        app: The FastAPI application instance
        include_security: Whether to include security headers middleware (default: True)
    
    Execution order:
        1. ErrorLoggingMiddleware (catches all errors)
        2. TimingMiddleware (measures total time)
        3. SecurityHeadersMiddleware (adds security headers)
        4. RequestIDMiddleware (adds request ID first)
    """
    
    # Add middlewares in reverse order of desired execution
    
    # 1. Error logging (outermost - catches everything)
    app.add_middleware(ErrorLoggingMiddleware)
    logger.info("Registered ErrorLoggingMiddleware")
    
    # 2. Timing middleware
    app.add_middleware(TimingMiddleware)
    logger.info("Registered TimingMiddleware")
    
    # 3. Security headers
    if include_security:
        app.add_middleware(SecurityHeadersMiddleware)
        logger.info("Registered SecurityHeadersMiddleware")
    
    # 4. Request ID (innermost - runs first)
    app.add_middleware(RequestIDMiddleware)
    logger.info("Registered RequestIDMiddleware")
    
    logger.info(
        "Core middlewares registered successfully",
        extra={
            "middlewares": [
                "RequestIDMiddleware",
                "SecurityHeadersMiddleware" if include_security else None,
                "TimingMiddleware",
                "ErrorLoggingMiddleware",
            ],
            "count": 4 if include_security else 3,
        }
    )


# Utility function to get request ID from current request
def get_request_id(request: Request) -> Optional[str]:
    """
    Utility function to retrieve the request ID from the current request.
    
    Args:
        request: The current FastAPI Request object
        
    Returns:
        The request ID string, or None if not available
    """
    return getattr(request.state, "request_id", None)


__all__ = [
    "RequestIDMiddleware",
    "TimingMiddleware",
    "SecurityHeadersMiddleware",
    "ErrorLoggingMiddleware",
    "register_middlewares",
    "get_request_id",
]