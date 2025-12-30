"""
API v1 Router
Main router that includes all API v1 endpoints
"""
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

# Create main API v1 router
router = APIRouter()

# Import and include routers that exist
try:
    from app.api.v1.endpoints import auth
    router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
except ImportError as e:
    logger.warning(f"Could not import auth router: {e}")

try:
    from app.api.v1.endpoints import users
    router.include_router(users.router, prefix="/users", tags=["Users"])
except ImportError as e:
    logger.warning(f"Could not import users router: {e}")

try:
    from app.api.v1.endpoints import rooms
    router.include_router(rooms.router, prefix="/rooms", tags=["Rooms"])
except ImportError as e:
    logger.warning(f"Could not import rooms router: {e}")

try:
    from app.api.v1.endpoints import bookings
    router.include_router(bookings.router, prefix="/bookings", tags=["Bookings"])
except ImportError as e:
    logger.warning(f"Could not import bookings router: {e}")

try:
    from app.api.v1.endpoints import payments
    router.include_router(payments.router, prefix="/payments", tags=["Payments"])
except ImportError as e:
    logger.warning(f"Could not import payments router: {e}")

try:
    from app.api.v1.endpoints import maintenance
    router.include_router(maintenance.router, prefix="/maintenance", tags=["Maintenance"])
except ImportError as e:
    logger.warning(f"Could not import maintenance router: {e}")

try:
    from app.api.v1.endpoints import announcements
    router.include_router(announcements.router, prefix="/announcements", tags=["Announcements"])
except ImportError as e:
    logger.warning(f"Could not import announcements router: {e}")

try:
    from app.api.v1.endpoints import notifications
    router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
except ImportError as e:
    logger.warning(f"Could not import notifications router: {e}")

try:
    from app.api.v1.endpoints import reports
    router.include_router(reports.router, prefix="/reports", tags=["Reports"])
except ImportError as e:
    logger.warning(f"Could not import reports router: {e}")

try:
    from app.api.v1.endpoints import settings
    router.include_router(settings.router, prefix="/settings", tags=["Settings"])
except ImportError as e:
    logger.warning(f"Could not import settings router: {e}")

try:
    from app.api.v1.endpoints import dashboard
    router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
except ImportError as e:
    logger.warning(f"Could not import dashboard router: {e}")

try:
    from app.api.v1.endpoints import analytics
    router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
except ImportError as e:
    logger.warning(f"Could not import analytics router: {e}")

try:
    from app.api.v1.endpoints import check_in_out
    router.include_router(check_in_out.router, prefix="/check-in-out", tags=["Check-In/Out"])
except ImportError as e:
    logger.warning(f"Could not import check_in_out router: {e}")

try:
    from app.api.v1.endpoints import complaints
    router.include_router(complaints.router, prefix="/complaints", tags=["Complaints"])
except ImportError as e:
    logger.warning(f"Could not import complaints router: {e}")

try:
    from app.api.v1.endpoints import expenses
    router.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])
except ImportError as e:
    logger.warning(f"Could not import expenses router: {e}")

try:
    from app.api.v1.endpoints import inventory
    router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
except ImportError as e:
    logger.warning(f"Could not import inventory router: {e}")

try:
    from app.api.v1.endpoints import staff
    router.include_router(staff.router, prefix="/staff", tags=["Staff"])
except ImportError as e:
    logger.warning(f"Could not import staff router: {e}")

try:
    from app.api.v1.endpoints import visitors
    router.include_router(visitors.router, prefix="/visitors", tags=["Visitors"])
except ImportError as e:
    logger.warning(f"Could not import visitors router: {e}")

# Health check endpoint
@router.get("/health", tags=["Health"])
async def health_check():
    """API v1 health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "api": "v1"
    }

logger.info("API v1 router initialized successfully")