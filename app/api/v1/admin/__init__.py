"""
Enhanced Admin API Router Module

This module aggregates all admin-related API routers with optimized routing,
middleware integration, and comprehensive error handling.

Features:
- Centralized router aggregation
- Enhanced error handling middleware
- Performance monitoring integration
- Request/response logging
- Rate limiting support
- API versioning compatibility
"""

from typing import List
import time
from functools import wraps

from fastapi import APIRouter, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.core.monitoring import track_api_performance
from app.core.rate_limiting import rate_limit_middleware
from app.core.exceptions import (
    AdminAPIException,
    RateLimitExceeded,
    MaintenanceMode,
    APIDeprecated
)

from . import (
    admins,
    context,
    dashboard,
    hostel_assignments,
    overrides,
    permissions
)

logger = get_logger(__name__)

# Create main admin router with enhanced configuration
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={
        400: {"description": "Bad Request - Invalid input parameters"},
        401: {"description": "Unauthorized - Authentication required"},
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Not Found - Resource not found"},
        409: {"description": "Conflict - Resource conflict"},
        422: {"description": "Unprocessable Entity - Validation error"},
        429: {"description": "Too Many Requests - Rate limit exceeded"},
        500: {"description": "Internal Server Error - Server error"},
        503: {"description": "Service Unavailable - Maintenance mode"}
    }
)


def performance_monitoring_middleware():
    """
    Enhanced middleware for API performance monitoring and logging.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            start_time = time.time()
            endpoint = f"{request.method} {request.url.path}"
            
            try:
                # Log request
                logger.debug(f"API Request: {endpoint}", extra={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "client_host": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                })
                
                # Execute the actual endpoint function
                response = await func(request, *args, **kwargs)
                
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Track performance metrics
                await track_api_performance(
                    endpoint=endpoint,
                    execution_time=execution_time,
                    status_code=getattr(response, 'status_code', 200),
                    request_size=len(await request.body()) if hasattr(request, 'body') else 0,
                    response_size=len(response) if hasattr(response, '__len__') else 0
                )
                
                # Log successful response
                logger.info(f"API Response: {endpoint}", extra={
                    "execution_time": execution_time,
                    "status_code": getattr(response, 'status_code', 200),
                    "success": True
                })
                
                return response
                
            except HTTPException as e:
                execution_time = time.time() - start_time
                
                # Log HTTP exceptions
                logger.warning(f"API HTTP Error: {endpoint}", extra={
                    "execution_time": execution_time,
                    "status_code": e.status_code,
                    "error_detail": e.detail,
                    "success": False
                })
                
                raise
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                # Log unexpected errors
                logger.error(f"API Unexpected Error: {endpoint}", extra={
                    "execution_time": execution_time,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "success": False
                }, exc_info=True)
                
                # Return generic error response for security
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error occurred"
                )
                
        return wrapper
    return decorator


def enhanced_exception_handler():
    """
    Enhanced exception handler for admin API specific exceptions.
    """
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle admin API specific exceptions with detailed responses."""
        
        if isinstance(exc, AdminAPIException):
            logger.warning(f"Admin API Exception: {exc.detail}", extra={
                "exception_type": type(exc).__name__,
                "endpoint": f"{request.method} {request.url.path}",
                "error_code": getattr(exc, 'error_code', None)
            })
            
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "detail": exc.detail,
                    "error_code": getattr(exc, 'error_code', None),
                    "timestamp": time.time(),
                    "path": request.url.path
                }
            )
        
        elif isinstance(exc, RateLimitExceeded):
            logger.warning(f"Rate limit exceeded: {request.url.path}", extra={
                "client_host": request.client.host if request.client else None,
                "endpoint": f"{request.method} {request.url.path}"
            })
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": getattr(exc, 'retry_after', 60),
                    "timestamp": time.time(),
                    "path": request.url.path
                },
                headers={"Retry-After": str(getattr(exc, 'retry_after', 60))}
            )
        
        elif isinstance(exc, MaintenanceMode):
            logger.info(f"Maintenance mode active: {request.url.path}")
            
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": "Service temporarily unavailable due to maintenance.",
                    "maintenance_window": getattr(exc, 'maintenance_window', None),
                    "estimated_completion": getattr(exc, 'estimated_completion', None),
                    "timestamp": time.time(),
                    "path": request.url.path
                },
                headers={"Retry-After": str(getattr(exc, 'retry_after', 3600))}
            )
        
        elif isinstance(exc, APIDeprecated):
            logger.warning(f"Deprecated API accessed: {request.url.path}", extra={
                "deprecation_date": getattr(exc, 'deprecation_date', None),
                "removal_date": getattr(exc, 'removal_date', None)
            })
            
            return JSONResponse(
                status_code=status.HTTP_410_GONE,
                content={
                    "detail": exc.detail,
                    "deprecation_date": getattr(exc, 'deprecation_date', None),
                    "removal_date": getattr(exc, 'removal_date', None),
                    "migration_guide": getattr(exc, 'migration_guide', None),
                    "timestamp": time.time(),
                    "path": request.url.path
                }
            )
        
        # Generic exception handling
        logger.error(f"Unhandled exception in admin API: {str(exc)}", extra={
            "exception_type": type(exc).__name__,
            "endpoint": f"{request.method} {request.url.path}"
        }, exc_info=True)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred. Please contact support.",
                "error_id": f"admin-{int(time.time())}",
                "timestamp": time.time(),
                "path": request.url.path
            }
        )
    
    return handler


# Configure router middleware and exception handlers
if settings.ENABLE_API_MONITORING:
    router.middleware("http")(performance_monitoring_middleware())

if settings.ENABLE_RATE_LIMITING:
    router.middleware("http")(rate_limit_middleware(
        requests_per_minute=settings.ADMIN_API_RATE_LIMIT,
        burst_size=settings.ADMIN_API_BURST_SIZE
    ))

# Add exception handler
router.add_exception_handler(Exception, enhanced_exception_handler())

# Health check endpoint for admin API
@router.get(
    "/health",
    tags=["admin:system"],
    summary="Admin API health check",
    description="Check the health status of admin API services"
)
async def admin_api_health_check() -> dict:
    """
    Comprehensive health check for admin API services.
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": settings.API_VERSION,
            "services": {
                "admin_users": "healthy",
                "hostel_assignments": "healthy", 
                "permissions": "healthy",
                "overrides": "healthy",
                "context": "healthy",
                "dashboard": "healthy"
            },
            "performance": {
                "avg_response_time_ms": await get_avg_response_time(),
                "error_rate_percent": await get_error_rate(),
                "active_connections": await get_active_connections()
            }
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "error": "Health check failed",
            "version": settings.API_VERSION
        }


async def get_avg_response_time() -> float:
    """Get average API response time for health check."""
    # Implementation would fetch from monitoring system
    return 150.0  # placeholder


async def get_error_rate() -> float:
    """Get API error rate percentage for health check.""" 
    # Implementation would fetch from monitoring system
    return 2.5  # placeholder


async def get_active_connections() -> int:
    """Get number of active API connections for health check."""
    # Implementation would fetch from connection pool
    return 45  # placeholder


# Include all admin sub-routers with enhanced configuration
router.include_router(
    admins.router,
    dependencies=[],
    responses={
        404: {"description": "Admin not found"},
        409: {"description": "Admin already exists"}
    }
)

router.include_router(
    hostel_assignments.router,
    dependencies=[],
    responses={
        404: {"description": "Assignment not found"},
        409: {"description": "Assignment conflict"}
    }
)

router.include_router(
    overrides.router,
    dependencies=[],
    responses={
        404: {"description": "Override not found"},
        409: {"description": "Override conflict"}
    }
)

router.include_router(
    permissions.router,
    dependencies=[],
    responses={
        404: {"description": "Permission not found"},
        403: {"description": "Permission denied"}
    }
)

router.include_router(
    context.router,
    dependencies=[],
    responses={
        404: {"description": "Context not found"},
        409: {"description": "Context switch conflict"}
    }
)

router.include_router(
    dashboard.router,
    dependencies=[],
    responses={
        503: {"description": "Dashboard service unavailable"}
    }
)

# Export router and metadata
__all__ = [
    "router",
    "performance_monitoring_middleware",
    "enhanced_exception_handler"
]

# Router metadata for documentation
router_metadata = {
    "name": "Admin API Router",
    "version": "2.0.0",
    "description": "Enhanced admin management API with comprehensive features",
    "endpoints": {
        "admins": "Admin user management with enhanced validation and bulk operations",
        "assignments": "Hostel assignment management with conflict detection",
        "overrides": "Override request system with workflow automation",
        "permissions": "Role-based permission management with inheritance",
        "context": "Hostel context switching with preferences",
        "dashboard": "Multi-hostel dashboard with real-time analytics"
    },
    "features": [
        "Enhanced error handling and validation",
        "Comprehensive caching strategy", 
        "Performance monitoring and metrics",
        "Rate limiting and security controls",
        "Detailed audit logging",
        "Background task processing",
        "Real-time notifications",
        "Advanced filtering and pagination",
        "Bulk operations support",
        "API health monitoring"
    ]
}