"""
Visitor dashboard endpoints.

This module provides endpoints for retrieving various dashboard views:
- Full dashboard with all widgets
- Lightweight summary for quick display
- Activity timeline
- Personalized quick actions
"""

from typing import Annotated, Dict, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_visitor_dashboard_service
from app.schemas.visitor import (
    VisitorDashboard,
    DashboardSummary,
    ActivityTimeline,
    QuickActions,
)
from app.services.visitor.visitor_dashboard_service import VisitorDashboardService

# Type aliases for cleaner dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
DashboardServiceDep = Annotated[VisitorDashboardService, Depends(get_visitor_dashboard_service)]

router = APIRouter(
    prefix="/visitors/me/dashboard",
    tags=["Visitors - Dashboard"],
)


@router.get(
    "",
    response_model=VisitorDashboard,
    summary="Get full visitor dashboard",
    description="Returns the complete dashboard payload for the current visitor including all widgets and data.",
    responses={
        200: {
            "description": "Dashboard data retrieved successfully",
            "model": VisitorDashboard,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Visitor profile not found"},
    },
)
async def get_dashboard(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
) -> VisitorDashboard:
    """
    Retrieve the complete dashboard for the current visitor.

    Includes:
    - Summary statistics
    - Recent activity
    - Recommended hostels
    - Quick actions
    - Saved searches
    - Favorite hostels

    Args:
        current_user: Authenticated user from dependency injection
        dashboard_service: Dashboard service instance

    Returns:
        VisitorDashboard: Complete dashboard data

    Raises:
        HTTPException: If dashboard data cannot be retrieved
    """
    result = await dashboard_service.get_dashboard(user_id=current_user.id)
    return result.unwrap()


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Get dashboard summary",
    description="Returns a lightweight dashboard summary for quick display and reduced bandwidth.",
    responses={
        200: {
            "description": "Dashboard summary retrieved successfully",
            "model": DashboardSummary,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_dashboard_summary(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
) -> DashboardSummary:
    """
    Retrieve a lightweight dashboard summary.

    Optimized for:
    - Quick loading
    - Mobile devices
    - Reduced bandwidth usage

    Args:
        current_user: Authenticated user from dependency injection
        dashboard_service: Dashboard service instance

    Returns:
        DashboardSummary: Lightweight dashboard summary

    Raises:
        HTTPException: If summary cannot be retrieved
    """
    result = await dashboard_service.get_dashboard_summary(user_id=current_user.id)
    return result.unwrap()


@router.get(
    "/activity",
    response_model=ActivityTimeline,
    summary="Get activity timeline",
    description="Returns recent activity timeline including searches, views, inquiries, and bookings.",
    responses={
        200: {
            "description": "Activity timeline retrieved successfully",
            "model": ActivityTimeline,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_activity_timeline(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of activity items to return"
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Number of days to look back for activities"
    ),
) -> ActivityTimeline:
    """
    Retrieve the activity timeline for the current visitor.

    Activity types included:
    - Hostel searches
    - Hostel views
    - Inquiries sent
    - Bookings made
    - Favorites added/removed
    - Reviews posted

    Args:
        current_user: Authenticated user from dependency injection
        dashboard_service: Dashboard service instance
        limit: Maximum number of activity items (1-100)
        days: Number of days to look back (1-365)

    Returns:
        ActivityTimeline: Chronological list of recent activities

    Raises:
        HTTPException: If timeline cannot be retrieved
    """
    result = await dashboard_service.get_activity_timeline(
        user_id=current_user.id,
        limit=limit,
        days=days
    )
    return result.unwrap()


@router.get(
    "/quick-actions",
    response_model=QuickActions,
    summary="Get personalized quick actions",
    description="Returns recommended quick actions based on visitor behavior and context.",
    responses={
        200: {
            "description": "Quick actions retrieved successfully",
            "model": QuickActions,
        },
        401: {"description": "Authentication required"},
    },
)
async def get_quick_actions(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
) -> QuickActions:
    """
    Retrieve personalized quick actions for the dashboard.

    Actions are dynamically generated based on:
    - Visitor behavior patterns
    - Incomplete actions
    - Trending hostels
    - Personalized recommendations
    - Seasonal promotions

    Args:
        current_user: Authenticated user from dependency injection
        dashboard_service: Dashboard service instance

    Returns:
        QuickActions: List of recommended actions

    Raises:
        HTTPException: If actions cannot be retrieved
    """
    result = await dashboard_service.get_quick_actions(user_id=current_user.id)
    return result.unwrap()


@router.post(
    "/refresh",
    response_model=VisitorDashboard,
    summary="Refresh dashboard data",
    description="Force refresh all dashboard data and return updated payload.",
    responses={
        200: {
            "description": "Dashboard refreshed successfully",
            "model": VisitorDashboard,
        },
        401: {"description": "Authentication required"},
    },
)
async def refresh_dashboard(
    current_user: CurrentUser,
    dashboard_service: DashboardServiceDep,
) -> VisitorDashboard:
    """
    Force refresh all dashboard data.

    Useful for:
    - Getting latest data after actions
    - Manual refresh requests
    - Cache invalidation

    Args:
        current_user: Authenticated user from dependency injection
        dashboard_service: Dashboard service instance

    Returns:
        VisitorDashboard: Refreshed complete dashboard data

    Raises:
        HTTPException: If refresh fails
    """
    result = await dashboard_service.refresh_dashboard(user_id=current_user.id)
    return result.unwrap()