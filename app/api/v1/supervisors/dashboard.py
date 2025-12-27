"""
Supervisor Dashboard and Analytics

Provides aggregated dashboard data, metrics, alerts, and tasks for supervisors.
Optimized for dashboard UI consumption with caching support.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.core.dependencies import AuthenticationDependency
from app.services.supervisor.supervisor_dashboard_service import SupervisorDashboardService
from app.schemas.supervisor import (
    SupervisorDashboardAnalytics,
    SupervisorDashboardMetrics,
    SupervisorDashboardAlerts,
    SupervisorRecentTasks,
)

# Router configuration
router = APIRouter(
    prefix="",
    tags=["Supervisors - Dashboard"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_dashboard_service() -> SupervisorDashboardService:
    """
    Dependency provider for SupervisorDashboardService.
    
    Wire this to your DI container or service factory.
    """
    raise NotImplementedError(
        "SupervisorDashboardService dependency must be implemented."
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """Extract and validate current authenticated user."""
    user = auth.get_current_user()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user


# ============================================================================
# Request/Response Models
# ============================================================================

class DashboardRefreshResponse(BaseModel):
    """Response for dashboard cache refresh"""
    status: str = Field(..., description="Refresh status")
    message: str = Field(..., description="Refresh result message")
    refreshed_at: str = Field(..., description="Timestamp of refresh")
    cache_ttl: Optional[int] = Field(None, description="Cache TTL in seconds")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/{supervisor_id}/dashboard",
    response_model=SupervisorDashboardAnalytics,
    summary="Get supervisor dashboard",
    description="""
    Get comprehensive dashboard analytics for a supervisor.
    
    **Dashboard Components**:
    - **Overview Metrics**: Activity counts, assignment status, performance scores
    - **Recent Activities**: Latest check-ins, tasks, interactions
    - **Alerts & Notifications**: Pending items, warnings, urgent matters
    - **Performance Summary**: Current period metrics and trends
    - **Quick Actions**: Common tasks and shortcuts
    - **Schedules**: Upcoming shifts and assignments
    
    **Optimization**:
    - Cached for performance (default 5 min TTL)
    - Optimized queries for dashboard widgets
    - Aggregated data for faster loading
    
    **Use Cases**:
    - Main dashboard view
    - Mobile app home screen
    - Quick status overview
    """,
    responses={
        200: {"description": "Dashboard data retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_dashboard(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    dashboard_service: SupervisorDashboardService = Depends(get_dashboard_service),
    current_user: Any = Depends(get_current_user),
    use_cache: bool = Query(True, description="Use cached data if available"),
) -> SupervisorDashboardAnalytics:
    """Get comprehensive dashboard analytics."""
    result = dashboard_service.get_dashboard(
        supervisor_id=supervisor_id,
        use_cache=use_cache,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{supervisor_id}/dashboard/metrics",
    response_model=SupervisorDashboardMetrics,
    summary="Get dashboard metrics only",
    description="""
    Get core dashboard metrics without full dashboard data.
    
    **Metrics Include**:
    - Total activities (today, this week, this month)
    - Active assignments count
    - Pending tasks count
    - Student interactions count
    - Incident reports count
    - Performance rating
    - Attendance percentage
    - Compliance score
    
    **Lightweight Endpoint**:
    - Faster than full dashboard
    - Optimized for metric widgets
    - Minimal data transfer
    
    **Use Cases**:
    - Metric cards/widgets
    - Status indicators
    - Quick stats API
    """,
    responses={
        200: {"description": "Metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_dashboard_metrics(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    dashboard_service: SupervisorDashboardService = Depends(get_dashboard_service),
    current_user: Any = Depends(get_current_user),
    period: str = Query("today", regex="^(today|week|month|year)$", description="Metrics period"),
) -> SupervisorDashboardMetrics:
    """Get core dashboard metrics for specified period."""
    result = dashboard_service.get_dashboard_metrics(
        supervisor_id=supervisor_id,
        period=period,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{supervisor_id}/dashboard/alerts",
    response_model=SupervisorDashboardAlerts,
    summary="Get dashboard alerts",
    description="""
    Get active alerts and notifications for supervisor dashboard.
    
    **Alert Types**:
    - **Urgent**: Immediate attention required
    - **Warning**: Important but not critical
    - **Info**: General notifications
    - **Success**: Positive confirmations
    
    **Alert Categories**:
    - Pending tasks and assignments
    - Compliance issues
    - Performance warnings
    - Schedule conflicts
    - System notifications
    - Student-related alerts
    
    **Priority Ordering**: Urgent first, then by timestamp
    
    **Use Cases**:
    - Notification center
    - Alert badges
    - Action items list
    """,
    responses={
        200: {"description": "Alerts retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_dashboard_alerts(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    dashboard_service: SupervisorDashboardService = Depends(get_dashboard_service),
    current_user: Any = Depends(get_current_user),
    severity: Optional[str] = Query(
        None, 
        regex="^(urgent|warning|info|success)$",
        description="Filter by alert severity"
    ),
    unread_only: bool = Query(False, description="Return only unread alerts"),
    limit: int = Query(10, ge=1, le=50, description="Maximum alerts to return"),
) -> SupervisorDashboardAlerts:
    """Get active alerts and notifications."""
    result = dashboard_service.get_dashboard_alerts(
        supervisor_id=supervisor_id,
        filters={
            "severity": severity,
            "unread_only": unread_only,
            "limit": limit,
        },
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.get(
    "/{supervisor_id}/dashboard/tasks/recent",
    response_model=SupervisorRecentTasks,
    summary="Get recent tasks for supervisor",
    description="""
    Get recent tasks and assignments for supervisor.
    
    **Task Types**:
    - Scheduled duties
    - Incident follow-ups
    - Maintenance checks
    - Administrative tasks
    - Student interactions
    - Report submissions
    
    **Task Status**:
    - Pending: Not yet started
    - In Progress: Currently working
    - Completed: Finished
    - Overdue: Past deadline
    
    **Ordering**: Due date (ascending), then priority (descending)
    
    **Use Cases**:
    - Task list widget
    - To-do items
    - Work queue
    """,
    responses={
        200: {"description": "Tasks retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_recent_tasks(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    dashboard_service: SupervisorDashboardService = Depends(get_dashboard_service),
    current_user: Any = Depends(get_current_user),
    status: Optional[str] = Query(
        None,
        regex="^(pending|in_progress|completed|overdue)$",
        description="Filter by task status"
    ),
    limit: int = Query(10, ge=1, le=50, description="Maximum tasks to return"),
    include_completed: bool = Query(False, description="Include completed tasks"),
) -> SupervisorRecentTasks:
    """Get recent tasks with optional filtering."""
    result = dashboard_service.get_recent_tasks(
        supervisor_id=supervisor_id,
        filters={
            "status": status,
            "limit": limit,
            "include_completed": include_completed,
        },
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{supervisor_id}/dashboard/refresh",
    response_model=DashboardRefreshResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Refresh dashboard cache",
    description="""
    Force refresh of dashboard cache for a supervisor.
    
    **Refresh Process**:
    1. Invalidates current cache
    2. Recalculates all metrics
    3. Regenerates dashboard data
    4. Updates cache with new data
    
    **Use Cases**:
    - User-triggered refresh
    - After major data changes
    - Cache corruption recovery
    - Real-time data requirement
    
    **Note**: 
    - Async operation (returns 202 Accepted)
    - May take a few seconds to complete
    - Rate limited to prevent abuse
    - Next dashboard request will get fresh data
    
    **Rate Limits**:
    - Max 1 refresh per minute per supervisor
    - Admin users have higher limits
    """,
    responses={
        202: {"description": "Refresh initiated successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
        429: {"description": "Too many refresh requests"},
    }
)
async def refresh_dashboard_cache(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    dashboard_service: SupervisorDashboardService = Depends(get_dashboard_service),
    current_user: Any = Depends(get_current_user),
    force: bool = Query(False, description="Force refresh even if recently refreshed"),
) -> DashboardRefreshResponse:
    """Force refresh dashboard cache."""
    result = dashboard_service.refresh_dashboard_cache(
        supervisor_id=supervisor_id,
        force=force,
        requested_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        if "rate limit" in error_msg or "too many" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Dashboard refresh rate limit exceeded. Please wait before trying again."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return DashboardRefreshResponse(**result.unwrap())


@router.post(
    "/{supervisor_id}/dashboard/alerts/{alert_id}/mark-read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark alert as read",
    description="""
    Mark a specific dashboard alert as read.
    
    **Effects**:
    - Updates alert read status
    - Decreases unread count
    - Updates dashboard cache
    
    **Use Cases**:
    - User dismisses notification
    - Alert acknowledgment
    - Notification center management
    """,
    responses={
        204: {"description": "Alert marked as read"},
        401: {"description": "Authentication required"},
        404: {"description": "Alert not found"},
    }
)
async def mark_alert_read(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    alert_id: str = Path(..., description="Unique alert identifier"),
    dashboard_service: SupervisorDashboardService = Depends(get_dashboard_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """Mark alert as read."""
    result = dashboard_service.mark_alert_read(
        supervisor_id=supervisor_id,
        alert_id=alert_id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert with ID '{alert_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.post(
    "/{supervisor_id}/dashboard/alerts/mark-all-read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all alerts as read",
    description="""
    Mark all alerts for a supervisor as read.
    
    **Effects**:
    - Updates all unread alerts to read status
    - Clears unread count
    - Updates dashboard cache
    
    **Use Cases**:
    - Clear all notifications
    - Bulk acknowledgment
    """,
    responses={
        204: {"description": "All alerts marked as read"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def mark_all_alerts_read(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    dashboard_service: SupervisorDashboardService = Depends(get_dashboard_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """Mark all alerts as read."""
    result = dashboard_service.mark_all_alerts_read(supervisor_id=supervisor_id)
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )