"""
Leave Calendar API Endpoints.

Provides calendar views and scheduling information:
- Monthly calendar views
- Hostel-wide leave schedules
- Student personal calendars
- Conflict detection
- Occupancy tracking

Useful for planning and resource management.
"""
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.api.v1.leaves.dependencies import (
    CalendarParams,
    get_calendar_params,
    get_leave_calendar_service,
    get_target_student_id,
    verify_student_or_admin,
)
from app.schemas.leave.leave_calendar import (
    CalendarDay,
    CalendarEvent,
    HostelCalendarResponse,
    OccupancyStats,
    StudentCalendarResponse,
)
from app.services.leave.leave_calendar_service import LeaveCalendarService

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/leaves/calendar", tags=["leaves:calendar"])


# ============================================================================
# Hostel Calendar Endpoints
# ============================================================================

@router.get(
    "/hostel/{hostel_id}",
    response_model=HostelCalendarResponse,
    summary="Get hostel leave calendar",
    description="""
    Retrieve monthly calendar view for an entire hostel.
    
    **Permission**: Admins and Wardens
    
    **Returns**:
    - Day-by-day breakdown of leave applications
    - Student names and leave types
    - Occupancy statistics
    - Conflicting leaves detection
    
    **Use Cases**:
    - Planning hostel operations
    - Managing student capacity
    - Identifying peak leave periods
    """,
    responses={
        200: {"description": "Calendar retrieved successfully"},
        400: {"description": "Invalid date parameters"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    },
)
async def get_hostel_leave_calendar(
    hostel_id: str,
    calendar_params: CalendarParams = Depends(get_calendar_params),
    view_type: str = Query(
        "summary",
        regex="^(summary|detailed|compact)$",
        description="Calendar view type",
    ),
    include_pending: bool = Query(
        True,
        description="Include pending leave applications",
    ),
    _admin=Depends(deps.get_admin_user),
    service: LeaveCalendarService = Depends(get_leave_calendar_service),
) -> HostelCalendarResponse:
    """
    Get comprehensive monthly calendar for hostel leave management.
    
    Displays all approved (and optionally pending) leaves for the hostel.
    """
    try:
        calendar_data = service.hostel_month_calendar(
            hostel_id=hostel_id,
            year=calendar_params.year,
            month=calendar_params.month,
            view_type=view_type,
            include_pending=include_pending,
        )
        
        if not calendar_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hostel '{hostel_id}' not found or no data available",
            )
        
        return calendar_data
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve hostel calendar: {str(e)}",
        )


@router.get(
    "/hostel/{hostel_id}/occupancy",
    response_model=OccupancyStats,
    summary="Get hostel occupancy statistics",
    description="""
    Get occupancy and availability statistics for a hostel.
    
    **Includes**:
    - Total capacity
    - Current occupancy
    - Students on leave
    - Day-by-day occupancy trends
    """,
)
async def get_hostel_occupancy_stats(
    hostel_id: str,
    calendar_params: CalendarParams = Depends(get_calendar_params),
    _admin=Depends(deps.get_admin_user),
    service: LeaveCalendarService = Depends(get_leave_calendar_service),
) -> OccupancyStats:
    """
    Get occupancy statistics for capacity planning and monitoring.
    """
    try:
        stats = service.get_occupancy_stats(
            hostel_id=hostel_id,
            year=calendar_params.year,
            month=calendar_params.month,
        )
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve occupancy stats: {str(e)}",
        )


# ============================================================================
# Student Calendar Endpoints
# ============================================================================

@router.get(
    "/student",
    response_model=StudentCalendarResponse,
    summary="Get student leave calendar",
    description="""
    Retrieve personal leave calendar for a student.
    
    **Permission**:
    - Students: Can view only their own calendar
    - Admins: Can view any student's calendar
    
    **Returns**:
    - Approved leaves
    - Pending applications
    - Available dates
    - Conflict warnings
    """,
)
async def get_student_leave_calendar(
    student_id: str = Depends(get_target_student_id),
    calendar_params: CalendarParams = Depends(get_calendar_params),
    include_pending: bool = Query(True, description="Include pending applications"),
    current_user=Depends(verify_student_or_admin),
    service: LeaveCalendarService = Depends(get_leave_calendar_service),
) -> StudentCalendarResponse:
    """
    Get personal monthly calendar showing student's leave schedule.
    """
    try:
        calendar_data = service.student_month_calendar(
            student_id=student_id,
            year=calendar_params.year,
            month=calendar_params.month,
            include_pending=include_pending,
        )
        
        if not calendar_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No calendar data found for student '{student_id}'",
            )
        
        return calendar_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve student calendar: {str(e)}",
        )


@router.get(
    "/student/{student_id}/upcoming",
    response_model=List[CalendarEvent],
    summary="Get upcoming leaves for student",
    description="Get list of upcoming approved leaves for a student",
)
async def get_upcoming_leaves(
    student_id: str,
    days_ahead: int = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to look ahead",
    ),
    current_user=Depends(verify_student_or_admin),
    service: LeaveCalendarService = Depends(get_leave_calendar_service),
) -> List[CalendarEvent]:
    """
    Get upcoming leaves for quick reference and planning.
    """
    try:
        # Permission check
        if current_user.role == "student" and current_user.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access other student's calendar",
            )
        
        upcoming = service.get_upcoming_leaves(
            student_id=student_id,
            days_ahead=days_ahead,
        )
        
        return upcoming
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve upcoming leaves: {str(e)}",
        )


# ============================================================================
# Conflict Detection Endpoints
# ============================================================================

@router.post(
    "/check-conflicts",
    summary="Check for leave conflicts",
    description="""
    Check if proposed leave dates conflict with existing leaves.
    
    **Useful for**:
    - Pre-validation before application
    - Avoiding overlapping leaves
    - Planning leave schedules
    """,
)
async def check_leave_conflicts(
    student_id: str = Query(...),
    start_date: str = Query(..., description="Proposed start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Proposed end date (YYYY-MM-DD)"),
    current_user=Depends(verify_student_or_admin),
    service: LeaveCalendarService = Depends(get_leave_calendar_service),
) -> dict[str, Any]:
    """
    Check for conflicts with existing leave applications.
    """
    try:
        # Permission check
        if current_user.role == "student" and current_user.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot check conflicts for other students",
            )
        
        conflicts = service.check_conflicts(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        return {
            "has_conflicts": len(conflicts) > 0,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "message": "No conflicts found" if not conflicts else "Conflicts detected",
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check conflicts: {str(e)}",
        )


# ============================================================================
# Calendar Export Endpoints
# ============================================================================

@router.get(
    "/export/ical",
    summary="Export calendar in iCal format",
    description="Export leave calendar in iCalendar format for external calendar apps",
)
async def export_calendar_ical(
    student_id: str = Depends(get_target_student_id),
    months: int = Query(3, ge=1, le=12, description="Months to export"),
    current_user=Depends(verify_student_or_admin),
    service: LeaveCalendarService = Depends(get_leave_calendar_service),
) -> Any:
    """
    Export calendar in iCal format for integration with external calendar applications.
    """
    try:
        ical_data = service.export_ical(
            student_id=student_id,
            months=months,
        )
        
        return ical_data
        
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="iCal export feature coming soon",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get(
    "/analytics/peak-periods",
    summary="Get peak leave periods",
    description="Identify peak leave periods for resource planning",
)
async def get_peak_leave_periods(
    hostel_id: str = Query(...),
    year: int = Query(..., ge=2000, le=2100),
    _admin=Depends(deps.get_admin_user),
    service: LeaveCalendarService = Depends(get_leave_calendar_service),
) -> dict[str, Any]:
    """
    Analyze and identify peak leave periods for planning purposes.
    """
    try:
        analytics = service.analyze_peak_periods(
            hostel_id=hostel_id,
            year=year,
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze peak periods: {str(e)}",
        )


@router.get(
    "/analytics/trends",
    summary="Get leave trends and patterns",
    description="Analyze leave trends over time for insights",
)
async def get_leave_trends(
    hostel_id: str = Query(...),
    period: str = Query("year", regex="^(month|quarter|year)$"),
    _admin=Depends(deps.get_admin_user),
    service: LeaveCalendarService = Depends(get_leave_calendar_service),
) -> dict[str, Any]:
    """
    Get leave trends and patterns for data-driven decision making.
    """
    try:
        trends = service.get_leave_trends(
            hostel_id=hostel_id,
            period=period,
        )
        
        return trends
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trends: {str(e)}",
        )