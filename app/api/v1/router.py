"""
API v1 Router - Main Entry Point
Aggregates all v1 API endpoints for the hostel management system
"""
from typing import List, Optional
 
from fastapi import APIRouter, Depends
import logging
 
from app.core.logging import get_logger
 
logger = get_logger(__name__)
 
# Create main API v1 router with proper configuration
router = APIRouter(
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"}
    }
)
 
# Track successful and failed imports for debugging
successful_imports = []
failed_imports = []
 
# Import and include existing sophisticated modules
def import_module_router(module_path: str, module_name: str, tags: Optional[List[str]] = None) -> bool:
    """Helper function to safely import and register module routers"""
    try:
        module = __import__(module_path, fromlist=[module_name])
        module_router = getattr(module, 'router')
       
        # Include router with or without additional tags
        if tags:
            router.include_router(module_router, tags=tags)
        else:
            router.include_router(module_router)
           
        successful_imports.append(module_name)
        logger.info(f"Successfully imported {module_name} router from {module_path}")
        return True
       
    except (ImportError, AttributeError) as e:
        failed_imports.append((module_name, str(e)))
        logger.warning(f"Could not import {module_name} router from {module_path}: {e}")
        return False
 
# Import the sophisticated modules that exist
import_module_router("app.api.v1.admin", "admin", ["Admin Management"])
import_module_router("app.api.v1.analytics", "analytics", ["Analytics & Reporting"])
import_module_router("app.api.v1.announcements", "announcements", ["Announcements"])
import_module_router("app.api.v1.attendance", "attendance", ["Attendance Management"])
import_module_router("app.api.v1.auth", "auth", ["Authentication & Authorization"])
import_module_router("app.api.v1.bookings", "bookings", ["Booking Management"])
import_module_router("app.api.v1.complaints", "complaints", ["Complaint Management"])
import_module_router("app.api.v1.fee_structures", "fee_structures", ["Fee Structures"])
import_module_router("app.api.v1.files", "files", ["File Management"])
import_module_router("app.api.v1.hostels", "hostels", ["Hostel Management"])
import_module_router("app.api.v1.inquiries", "inquiries", ["Inquiries Management"])
import_module_router("app.api.v1.leaves", "leaves", ["Leave Management"])       
import_module_router("app.api.v1.maintenance", "maintenance", ["Maintenance Management"])
import_module_router("app.api.v1.mess", "mess", ["Mess Management"])
import_module_router("app.api.v1.notifications", "notifications", ["Notifications"])
import_module_router("app.api.v1.payments", "payments", ["Payment Processing"])
import_module_router("app.api.v1.referrals", "referrals", ["Referrals Management"])
import_module_router("app.api.v1.reviews", "reviews", ["Reviews & Feedback"])
import_module_router("app.api.v1.rooms", "rooms", ["Room Management"])
import_module_router("app.api.v1.students", "students", ["Student Management"]) 
import_module_router("app.api.v1.subscriptions", "subscriptions", ["Subscriptions Management"])
import_module_router("app.api.v1.supervisors", "supervisors", ["Supervisor Management"])
import_module_router("app.api.v1.users", "users", ["User Management"])
import_module_router("app.api.v1.visitors", "visitors", ["Visitor Management"])
import_module_router("app.api.v1.webhooks", "webhooks", ["Webhooks"])



 
# Try to import legacy endpoint modules (if they exist)
legacy_modules = [
    ("app.api.v1.endpoints.auth", "auth", ["Authentication"]),
    ("app.api.v1.endpoints.users", "users", ["User Management"]),
    ("app.api.v1.endpoints.rooms", "rooms", ["Room Management"]),
    ("app.api.v1.endpoints.bookings", "bookings", ["Booking Management"]),
    ("app.api.v1.endpoints.payments", "payments", ["Payment Processing"]),
    ("app.api.v1.endpoints.maintenance", "maintenance", ["Maintenance"]),
    ("app.api.v1.endpoints.notifications", "notifications", ["Notifications"]),
    ("app.api.v1.endpoints.reports", "reports", ["Reports"]),
    ("app.api.v1.endpoints.settings", "settings", ["Settings"]),
    ("app.api.v1.endpoints.dashboard", "dashboard", ["Dashboard"]),
    ("app.api.v1.endpoints.check_in_out", "check_in_out", ["Check-In/Out"]),
    ("app.api.v1.endpoints.complaints", "complaints", ["Complaints"]),
    ("app.api.v1.endpoints.expenses", "expenses", ["Expenses"]),
    ("app.api.v1.endpoints.inventory", "inventory", ["Inventory"]),
    ("app.api.v1.endpoints.staff", "staff", ["Staff Management"]),
    ("app.api.v1.endpoints.visitors", "visitors", ["Visitor Management"])
    
]
 
for module_path, module_name, tags in legacy_modules:
    import_module_router(module_path, module_name, tags)
 
# Health and diagnostic endpoints
@router.get("/health", tags=["System Health"])
async def api_health_check():
    """
    Comprehensive API health check with module status
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "api_version": "v1",
        "loaded_modules": successful_imports,
        "failed_modules": [name for name, _ in failed_imports],
        "total_endpoints": len(successful_imports),
        "description": "Hostel Management System API v1"
    }
 
@router.get("/debug/modules", tags=["System Health"])
async def debug_module_status():
    """
    Debug endpoint showing detailed module import status
    """
    return {
        "successful_imports": {
            "count": len(successful_imports),
            "modules": successful_imports
        },
        "failed_imports": {
            "count": len(failed_imports),
            "details": [
                {"module": name, "error": str(error)}
                for name, error in failed_imports
            ]
        },
        "router_stats": {
            "total_routes": len(router.routes),
            "route_paths": [
                {
                    "path": route.path,
                    "methods": list(route.methods) if hasattr(route, 'methods') else [],
                    "name": route.name if hasattr(route, 'name') else "unnamed"
                }
                for route in router.routes
                if hasattr(route, 'path')
            ]
        }
    }
 
@router.get("/debug/openapi", tags=["System Health"])
async def debug_openapi_routes():
    """
    Debug endpoint to verify OpenAPI route registration
    """
    routes_info = []
    for route in router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes_info.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', 'unnamed'),
                "summary": getattr(route, 'summary', 'No summary'),
                "tags": getattr(route, 'tags', [])
            })
   
    return {
        "total_registered_routes": len(routes_info),
        "routes": routes_info,
        "modules_loaded": successful_imports
    }
 
# Log initialization status
logger.info(f"API v1 router initialized successfully")
logger.info(f"Loaded modules: {successful_imports}")
if failed_imports:
    logger.warning(f"Failed to load modules: {[name for name, _ in failed_imports]}")
 
# Export router info for external access
router_info = {
    "successful_imports": successful_imports,
    "failed_imports": failed_imports,
    "total_routes": len(router.routes)
}