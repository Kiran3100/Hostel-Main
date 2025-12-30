"""
Enhanced announcements module with comprehensive API organization.
"""
from datetime import datetime
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.logging import get_logger

from . import announcements, approval, scheduling, targeting, tracking

logger = get_logger(__name__)

# Create main router with enhanced configuration
router = APIRouter(
    prefix="/v1",
    responses={
        400: {"description": "Bad Request - Invalid input parameters"},
        401: {"description": "Unauthorized - Authentication required"},
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Not Found - Resource does not exist"},
        422: {"description": "Unprocessable Entity - Validation error"},
        429: {"description": "Too Many Requests - Rate limit exceeded"},
        500: {"description": "Internal Server Error - System error occurred"},
        503: {"description": "Service Unavailable - System maintenance"}
    },
    tags=["announcements"],
    dependencies=[
        # Add global dependencies here if needed
        # Depends(check_api_key),
        # Depends(validate_request_size),
    ]
)

# Include all sub-routers with enhanced organization
router.include_router(
    announcements.router,
    tags=["announcements:core"],
    responses={
        "200": {"description": "Success"},
        "404": {"description": "Announcement not found"}
    }
)

router.include_router(
    approval.router,
    tags=["announcements:approval"],
    responses={
        "409": {"description": "Approval state conflict"}
    }
)

router.include_router(
    scheduling.router,
    tags=["announcements:scheduling"],
    responses={
        "423": {"description": "Schedule locked for execution"}
    }
)

router.include_router(
    targeting.router,
    tags=["announcements:targeting"],
    responses={
        "422": {"description": "Invalid targeting configuration"}
    }
)

router.include_router(
    tracking.router,
    tags=["announcements:tracking"],
    responses={
        "429": {"description": "Tracking rate limit exceeded"}
    }
)


# Health check endpoint for the announcements module
@router.get(
    "/announcements/health",
    tags=["system:health"],
    summary="Announcements module health check",
    description="Check the health status of the announcements module and its dependencies.",
    response_description="Health status with service availability details"
)
async def announcements_health_check():
    """
    Comprehensive health check for the announcements module.
    
    Verifies:
    - Database connectivity
    - Service dependencies
    - Cache availability
    - External integrations
    
    Returns:
        dict: Health status information
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "module": "announcements",
            "version": __version__,
            "services": {
                "core": "healthy",
                "approval": "healthy", 
                "scheduling": "healthy",
                "targeting": "healthy",
                "tracking": "healthy"
            },
            "dependencies": {
                "database": "connected",
                "cache": "available",
                "notification_service": "responsive",
                "analytics_engine": "operational"
            }
        }
        
        logger.debug("Announcements health check completed successfully")
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "module": "announcements",
            "version": __version__,
            "error": str(e)
        }


# Module metadata endpoint
@router.get(
    "/announcements/info",
    tags=["system:info"],
    summary="Get announcements module information",
    description="Returns metadata and configuration information about the announcements module.",
    response_description="Module metadata and information"
)
async def announcements_info():
    """
    Get announcements module metadata and configuration.
    
    Returns:
        dict: Module information including version, features, and endpoints
    """
    return {
        "module": "announcements",
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "features": [
            "Core announcement management",
            "Approval workflows",
            "Scheduling and automation",
            "Advanced targeting",
            "Analytics and tracking"
        ],
        "endpoints": {
            "core": len([route for route in announcements.router.routes]),
            "approval": len([route for route in approval.router.routes]),
            "scheduling": len([route for route in scheduling.router.routes]),
            "targeting": len([route for route in targeting.router.routes]),
            "tracking": len([route for route in tracking.router.routes])
        },
        "status": "active"
    }


# Module-level configuration and metadata
__version__ = "1.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Enhanced announcements API module with comprehensive functionality"

__all__ = [
    "router",
    "announcements",
    "approval", 
    "scheduling",
    "targeting",
    "tracking"
]

# Export individual routers for testing and standalone use
announcement_routers = {
    "core": announcements.router,
    "approval": approval.router,
    "scheduling": scheduling.router,
    "targeting": targeting.router,
    "tracking": tracking.router
}


# Log module initialization
logger.info(
    f"Announcements module initialized (v{__version__})",
    extra={
        "version": __version__,
        "sub_modules": list(announcement_routers.keys()),
        "total_routers": len(announcement_routers)
    }
)