"""
Leave Management API Module Initialization.

This module aggregates all leave-related API endpoints:
- Leave Applications (core CRUD operations)
- Leave Approvals (workflow and decisions)
- Leave Balance (tracking and adjustments)
- Leave Calendar (scheduling and planning)

All routes are prefixed and properly tagged for OpenAPI documentation.
"""
from fastapi import APIRouter

from app.api.v1.leaves import approval, balance, calendar, leaves

# ============================================================================
# Router Aggregation
# ============================================================================

router = APIRouter()

# Include all sub-routers with proper organization
router.include_router(
    leaves.router,
    # Main leave operations - no additional prefix needed
    # Tags inherited from individual router
)

router.include_router(
    approval.router,
    # Approval workflow endpoints
    # Prefix: /leaves/approval
)

router.include_router(
    balance.router,
    # Balance tracking endpoints
    # Prefix: /leaves/balance
)

router.include_router(
    calendar.router,
    # Calendar and scheduling endpoints
    # Prefix: /leaves/calendar
)

# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    "router",
    "approval",
    "balance",
    "calendar",
    "leaves",
]


# ============================================================================
# API Documentation Metadata
# ============================================================================

# This metadata can be used for generating comprehensive API documentation
LEAVE_MODULE_INFO = {
    "name": "Leave Management System",
    "version": "1.0.0",
    "description": """
    Comprehensive leave management system for hostel administration.
    
    **Features**:
    - Student leave application submission
    - Multi-level approval workflow
    - Leave balance tracking
    - Calendar integration
    - Analytics and reporting
    
    **Modules**:
    - **Applications**: Core leave CRUD operations
    - **Approvals**: Workflow and decision management
    - **Balance**: Entitlement and usage tracking
    - **Calendar**: Scheduling and planning views
    """,
    "endpoints": {
        "applications": 8,
        "approvals": 7,
        "balance": 6,
        "calendar": 7,
    },
}