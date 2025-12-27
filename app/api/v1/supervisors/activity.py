"""
Supervisor Activity Tracking

Handles logging, retrieval, and analysis of supervisor activities including:
- Check-ins/check-outs
- Task completions
- Student interactions
- Incident reports
- Maintenance activities
"""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, validator

from app.core.dependencies import AuthenticationDependency
from app.services.supervisor.supervisor_activity_service import SupervisorActivityService
from app.schemas.supervisor import (
    SupervisorActivityCreate,
    SupervisorActivityBulkCreate,
    SupervisorActivityLogResponse,
    SupervisorActivitySummary,
    SupervisorActivityTimeline,
)

# Router configuration
router = APIRouter(
    prefix="",
    tags=["Supervisors - Activity"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_activity_service() -> SupervisorActivityService:
    """
    Dependency provider for SupervisorActivityService.
    
    Wire this to your DI container or service factory.
    """
    raise NotImplementedError(
        "SupervisorActivityService dependency must be implemented."
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

class ActivityFilters(BaseModel):
    """Filters for activity listing"""
    start_date: Optional[datetime] = Field(None, description="Filter activities from this date")
    end_date: Optional[datetime] = Field(None, description="Filter activities until this date")
    activity_type: Optional[str] = Field(None, description="Filter by activity type")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    
    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if v and 'start_date' in values and values['start_date']:
            if v < values['start_date']:
                raise ValueError('end_date must be after start_date')
        return v


class ActivityCountResponse(BaseModel):
    """Response for activity count endpoint"""
    total: int = Field(..., description="Total activity count")
    by_type: Optional[dict] = Field(None, description="Count breakdown by activity type")
    by_date: Optional[dict] = Field(None, description="Count breakdown by date")


class BulkActivityResponse(BaseModel):
    """Response for bulk activity logging"""
    created: int = Field(..., description="Number of activities successfully created")
    failed: int = Field(0, description="Number of activities that failed")
    errors: List[dict] = Field(default_factory=list, description="Error details for failed items")


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/{supervisor_id}/activity",
    response_model=SupervisorActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log supervisor activity",
    description="""
    Log a single supervisor activity entry.
    
    **Activity Types**:
    - check_in: Supervisor checking in for duty
    - check_out: Supervisor checking out from duty
    - student_interaction: Interaction with students
    - incident_report: Incident documentation
    - maintenance: Maintenance or inspection activity
    - meeting: Staff or administrative meeting
    - custom: Other custom activities
    
    **Automatically Captured**:
    - Timestamp
    - IP address
    - User agent
    - Geolocation (if available)
    """,
    responses={
        201: {"description": "Activity logged successfully"},
        400: {"description": "Invalid activity data"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def log_activity(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    payload: SupervisorActivityCreate = ...,
    activity_service: SupervisorActivityService = Depends(get_activity_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorActivityLogResponse:
    """Log a single supervisor activity entry."""
    result = activity_service.log_activity(
        supervisor_id=supervisor_id,
        data=payload.dict(exclude_unset=True),
        logged_by=current_user.id if hasattr(current_user, 'id') else None,
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
    "/activity/bulk",
    response_model=BulkActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk log activities",
    description="""
    Log multiple supervisor activities in a single request.
    
    **Use Cases**:
    - Batch import of historical activities
    - Offline activity synchronization
    - Automated activity logging from external systems
    
    **Behavior**:
    - Processes all activities atomically when possible
    - Returns detailed error information for failed items
    - Partial success is supported (some succeed, some fail)
    
    **Limits**:
    - Maximum 500 activities per request
    - Rate limited to prevent abuse
    """,
    responses={
        201: {"description": "Activities logged (check response for individual results)"},
        400: {"description": "Invalid request data"},
        401: {"description": "Authentication required"},
        413: {"description": "Payload too large (max 500 items)"},
    }
)
async def bulk_log_activities(
    payload: SupervisorActivityBulkCreate = ...,
    activity_service: SupervisorActivityService = Depends(get_activity_service),
    current_user: Any = Depends(get_current_user),
) -> BulkActivityResponse:
    """Log multiple supervisor activities in one operation."""
    # Validate bulk size
    if len(payload.activities) > 500:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Maximum 500 activities allowed per bulk request"
        )
    
    result = activity_service.bulk_log_activities(
        data_list=[activity.dict(exclude_unset=True) for activity in payload.activities],
        logged_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return BulkActivityResponse(**result.unwrap())


@router.get(
    "/{supervisor_id}/activity/summary",
    response_model=SupervisorActivitySummary,
    summary="Get activity summary",
    description="""
    Get aggregated activity summary for a supervisor.
    
    **Summary Includes**:
    - Total activity count
    - Breakdown by activity type
    - Average activities per day/week/month
    - Most active time periods
    - Compliance metrics
    - Trends and patterns
    
    **Filters**:
    - Date range for analysis period
    - Activity type grouping
    """,
    responses={
        200: {"description": "Summary retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_activity_summary(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    activity_service: SupervisorActivityService = Depends(get_activity_service),
    current_user: Any = Depends(get_current_user),
    start_date: Optional[datetime] = Query(None, description="Summary start date"),
    end_date: Optional[datetime] = Query(None, description="Summary end date"),
    group_by: str = Query("day", regex="^(day|week|month)$", description="Grouping period"),
) -> SupervisorActivitySummary:
    """Get aggregated activity summary for a supervisor."""
    filters = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "group_by": group_by,
    }
    
    result = activity_service.get_activity_summary(
        supervisor_id=supervisor_id,
        filters={k: v for k, v in filters.items() if v is not None},
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
    "/{supervisor_id}/activity",
    response_model=List[SupervisorActivityLogResponse],
    summary="List activities for supervisor",
    description="""
    List supervisor activities with pagination and filtering.
    
    **Sorting**:
    - Default: Most recent first
    - Supports custom sort fields
    
    **Filtering**:
    - Date range
    - Activity type
    - Location
    - Status
    
    Returns detailed activity logs with full context.
    """,
    responses={
        200: {"description": "Activities retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def list_activities(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    activity_service: SupervisorActivityService = Depends(get_activity_service),
    current_user: Any = Depends(get_current_user),
    start_date: Optional[datetime] = Query(None, description="Filter from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter until this date"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
) -> List[SupervisorActivityLogResponse]:
    """List supervisor activities with comprehensive filtering and pagination."""
    filters = ActivityFilters(
        start_date=start_date,
        end_date=end_date,
        activity_type=activity_type,
        page=page,
        page_size=page_size,
    )
    
    result = activity_service.list_activities(
        supervisor_id=supervisor_id,
        filters={
            **filters.dict(exclude_none=True),
            "sort_by": sort_by,
            "sort_order": sort_order,
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
    "/{supervisor_id}/activity/timeline",
    response_model=SupervisorActivityTimeline,
    summary="Get activity timeline",
    description="""
    Get supervisor activity timeline grouped by time period.
    
    **Timeline Views**:
    - Daily: Activities grouped by day
    - Weekly: Activities grouped by week
    - Monthly: Activities grouped by month
    
    **Visualization**:
    - Optimized for chart/graph rendering
    - Includes aggregated metrics per period
    - Shows trends and patterns over time
    
    Useful for activity trend analysis and reporting.
    """,
    responses={
        200: {"description": "Timeline retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_activity_timeline(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    activity_service: SupervisorActivityService = Depends(get_activity_service),
    current_user: Any = Depends(get_current_user),
    start_date: Optional[datetime] = Query(None, description="Timeline start date"),
    end_date: Optional[datetime] = Query(None, description="Timeline end date"),
    granularity: str = Query("day", regex="^(hour|day|week|month)$", description="Timeline granularity"),
) -> SupervisorActivityTimeline:
    """Get activity timeline with configurable grouping."""
    result = activity_service.get_activity_timeline(
        supervisor_id=supervisor_id,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        granularity=granularity,
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
    "/{supervisor_id}/activity/count",
    response_model=ActivityCountResponse,
    summary="Get activity count",
    description="""
    Get total count of activities with optional breakdowns.
    
    **Count Breakdowns**:
    - By activity type
    - By date/time period
    - By location
    - By status
    
    Lightweight endpoint for statistics and quick metrics.
    """,
    responses={
        200: {"description": "Count retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_activity_count(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    activity_service: SupervisorActivityService = Depends(get_activity_service),
    current_user: Any = Depends(get_current_user),
    start_date: Optional[datetime] = Query(None, description="Count from this date"),
    end_date: Optional[datetime] = Query(None, description="Count until this date"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type"),
    include_breakdown: bool = Query(True, description="Include detailed breakdowns"),
) -> ActivityCountResponse:
    """Get activity count with optional detailed breakdowns."""
    filters = {}
    if start_date:
        filters["start_date"] = start_date.isoformat()
    if end_date:
        filters["end_date"] = end_date.isoformat()
    if activity_type:
        filters["activity_type"] = activity_type
    
    result = activity_service.get_activity_count(
        supervisor_id=supervisor_id,
        filters=filters,
        include_breakdown=include_breakdown,
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
    
    return ActivityCountResponse(**result.unwrap())


@router.delete(
    "/{supervisor_id}/activity/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete activity log",
    description="""
    Delete a specific activity log entry.
    
    **Admin Operation**: Requires elevated privileges.
    
    **Warning**: This permanently removes the activity record.
    Use with caution as it affects audit trail.
    """,
    responses={
        204: {"description": "Activity deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Activity not found"},
    }
)
async def delete_activity(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    activity_id: str = Path(..., description="Unique activity identifier"),
    activity_service: SupervisorActivityService = Depends(get_activity_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """Delete a specific activity log entry."""
    result = activity_service.delete_activity(
        supervisor_id=supervisor_id,
        activity_id=activity_id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activity with ID '{activity_id}' not found"
            )
        if "permission" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete activity"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )