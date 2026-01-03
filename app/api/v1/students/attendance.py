"""
Student Attendance API Endpoints

Provides endpoints for students to view their attendance history, records,
check-in status, and summary statistics with comprehensive filtering and pagination.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field, ValidationError

from app.core.dependencies import get_current_user, get_attendance_service
from app.core.exceptions import (
    ServiceException,
    NotFoundError,
    ValidationException
)
from app.schemas.attendance import (
    AttendanceDetail,
    AttendanceListItem, 
    AttendanceResponse,
    AttendanceSummary,
    AttendanceFilterParams,
    AttendanceReport,
    DailyAttendanceSummary,
    CheckInStatus,
    CheckInHistory,
    WeeklySummary,
    MonthlyReport,
    TrendAnalysis
)
from app.schemas.common.pagination import PaginatedResponse, PaginationParams
from app.schemas.common.base import User
from app.schemas.common.enums import AttendanceStatus
from app.services.attendance.attendance_service import AttendanceService

router = APIRouter(
    prefix="/students/me/attendance",
    tags=["Students - Attendance"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=PaginatedResponse[AttendanceListItem],
    status_code=status.HTTP_200_OK,
    summary="Get my attendance history",
    description="Retrieve paginated attendance records for the currently authenticated student with optional filtering.",
    responses={
        200: {"description": "Attendance records retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        422: {"description": "Validation error - Invalid parameters"},
        500: {"description": "Internal server error"},
    },
)
async def get_my_attendance(
    start_date: Optional[date] = Query(
        None,
        description="Start date for attendance records (ISO format: YYYY-MM-DD)",
        example="2024-01-01",
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for attendance records (ISO format: YYYY-MM-DD)",
        example="2024-12-31",
    ),
    status_filter: Optional[AttendanceStatus] = Query(
        None,
        description="Filter by attendance status",
    ),
    late_only: Optional[bool] = Query(
        None,
        description="Filter only late arrivals",
    ),
    pagination: PaginationParams = Depends(),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[AttendanceListItem]:
    """
    Get attendance history for the authenticated student with pagination and filtering.
    
    Args:
        start_date: Optional start date for filtering records
        end_date: Optional end date for filtering records
        status_filter: Optional status filter
        late_only: Optional filter for late arrivals only
        pagination: Pagination parameters
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        PaginatedResponse[AttendanceListItem]: Paginated list of attendance records
        
    Raises:
        HTTPException: If retrieval fails or validation errors occur
    """
    try:
        # Validate date range
        if start_date and end_date and end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End date must be after or equal to start date"
            )

        # Build filter parameters
        filters = AttendanceFilterParams(
            student_id=current_user.id,
            date_from=start_date,
            date_to=end_date,
            status=status_filter,
            late_only=late_only,
            **pagination.model_dump()
        )

        result = await attendance_service.get_student_attendance_paginated(
            filters=filters
        )
        return result

    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/{attendance_id}",
    response_model=AttendanceDetail,
    status_code=status.HTTP_200_OK,
    summary="Get specific attendance record details",
    description="Retrieve detailed information for a specific attendance record.",
)
async def get_my_attendance_record(
    attendance_id: str,
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> AttendanceDetail:
    """
    Get detailed information for a specific attendance record.
    
    Args:
        attendance_id: UUID of the attendance record
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        AttendanceDetail: Detailed attendance record information
        
    Raises:
        HTTPException: If record not found or access denied
    """
    try:
        result = await attendance_service.get_attendance_detail(
            attendance_id=attendance_id,
            student_id=current_user.id
        )
        return result

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )
    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/summary",
    response_model=AttendanceSummary,
    status_code=status.HTTP_200_OK,
    summary="Get my attendance summary statistics",
    description="Retrieve aggregated attendance statistics for the authenticated student with optional period filtering.",
)
async def get_my_attendance_summary(
    period: str = Query(
        "monthly",
        regex="^(weekly|monthly|semester|yearly)$",
        description="Summary period (weekly, monthly, semester, yearly)",
    ),
    month: Optional[int] = Query(
        None,
        ge=1,
        le=12,
        description="Filter by specific month (1-12)",
    ),
    year: Optional[int] = Query(
        None,
        ge=2000,
        le=2100,
        description="Filter by specific year",
    ),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> AttendanceSummary:
    """
    Get attendance summary with statistics like present/absent counts and percentage.
    
    Args:
        period: Summary period type
        month: Optional month filter
        year: Optional year filter
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        AttendanceSummary: Attendance summary with comprehensive statistics
    """
    try:
        result = await attendance_service.get_student_attendance_summary(
            student_id=current_user.id,
            period=period,
            month=month,
            year=year,
        )
        return result

    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/check-in/status",
    response_model=CheckInStatus,
    status_code=status.HTTP_200_OK,
    summary="Get my current check-in status",
    description="Retrieve current check-in status and active session information.",
)
async def get_my_check_in_status(
    include_history: bool = Query(
        False,
        description="Include recent check-in history"
    ),
    include_stats: bool = Query(
        False,
        description="Include monthly statistics"
    ),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> CheckInStatus:
    """
    Get current check-in status and session information.
    
    Args:
        include_history: Whether to include recent history
        include_stats: Whether to include monthly stats
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        CheckInStatus: Current check-in status and session details
    """
    try:
        result = await attendance_service.get_student_check_in_status(
            student_id=current_user.id,
            include_history=include_history,
            include_stats=include_stats
        )
        return result

    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/check-in/history",
    response_model=List[CheckInHistory],
    status_code=status.HTTP_200_OK,
    summary="Get my check-in history",
    description="Retrieve historical check-in/check-out records.",
)
async def get_my_check_in_history(
    days: int = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to retrieve history for"
    ),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> List[CheckInHistory]:
    """
    Get check-in/check-out history for specified number of days.
    
    Args:
        days: Number of days to retrieve history for
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        List[CheckInHistory]: List of historical check-in records
    """
    try:
        result = await attendance_service.get_student_check_in_history(
            student_id=current_user.id,
            days=days
        )
        return result

    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/daily/{date}",
    response_model=DailyAttendanceSummary,
    status_code=status.HTTP_200_OK,
    summary="Get daily attendance details",
    description="Retrieve detailed attendance information for a specific date.",
)
async def get_my_daily_attendance(
    date: date = Field(..., description="Date to retrieve attendance for"),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> DailyAttendanceSummary:
    """
    Get detailed attendance information for a specific date.
    
    Args:
        date: Specific date to retrieve attendance for
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        DailyAttendanceSummary: Daily attendance details
    """
    try:
        if date > datetime.now().date():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot retrieve attendance for future dates"
            )

        result = await attendance_service.get_student_daily_attendance(
            student_id=current_user.id,
            date=date
        )
        return result

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No attendance record found for the specified date"
        )
    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/weekly",
    response_model=WeeklySummary,
    status_code=status.HTTP_200_OK,
    summary="Get weekly attendance summary",
    description="Retrieve weekly attendance summary with trends and analysis.",
)
async def get_my_weekly_summary(
    week_offset: int = Query(
        0,
        ge=-52,
        le=0,
        description="Week offset from current week (0 = current week, -1 = last week, etc.)"
    ),
    include_daily_breakdown: bool = Query(
        True,
        description="Include day-by-day breakdown"
    ),
    include_trends: bool = Query(
        False,
        description="Include week-over-week trends"
    ),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> WeeklySummary:
    """
    Get weekly attendance summary with optional trends and daily breakdown.
    
    Args:
        week_offset: Week offset from current week
        include_daily_breakdown: Whether to include daily breakdown
        include_trends: Whether to include trend analysis
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        WeeklySummary: Weekly attendance summary
    """
    try:
        result = await attendance_service.get_student_weekly_summary(
            student_id=current_user.id,
            week_offset=week_offset,
            include_daily_breakdown=include_daily_breakdown,
            include_trends=include_trends
        )
        return result

    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/monthly/{year}/{month}",
    response_model=AttendanceReport,
    status_code=status.HTTP_200_OK,
    summary="Get monthly attendance report",
    description="Retrieve comprehensive monthly attendance report with analytics.",
)
async def get_my_monthly_report(
    year: int = Field(..., ge=2000, le=2100, description="Year"),
    month: int = Field(..., ge=1, le=12, description="Month (1-12)"),
    include_trends: bool = Query(
        True,
        description="Include trend analysis"
    ),
    include_daily_records: bool = Query(
        True,
        description="Include daily attendance records"
    ),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> AttendanceReport:
    """
    Get comprehensive monthly attendance report.
    
    Args:
        year: Year for the report
        month: Month for the report (1-12)
        include_trends: Whether to include trend analysis
        include_daily_records: Whether to include daily records
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        AttendanceReport: Comprehensive monthly report
    """
    try:
        # Validate future month
        current_date = datetime.now().date()
        if year > current_date.year or (year == current_date.year and month > current_date.month):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot generate report for future months"
            )

        result = await attendance_service.get_student_monthly_report(
            student_id=current_user.id,
            year=year,
            month=month,
            include_trends=include_trends,
            include_daily_records=include_daily_records
        )
        return result

    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/trends",
    response_model=TrendAnalysis,
    status_code=status.HTTP_200_OK,
    summary="Get attendance trends analysis",
    description="Retrieve attendance trends and pattern analysis over time.",
)
async def get_my_attendance_trends(
    period_months: int = Query(
        3,
        ge=1,
        le=12,
        description="Number of months to analyze trends for"
    ),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> TrendAnalysis:
    """
    Get attendance trends and pattern analysis.
    
    Args:
        period_months: Number of months to analyze
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        TrendAnalysis: Attendance trends and insights
    """
    try:
        result = await attendance_service.get_student_attendance_trends(
            student_id=current_user.id,
            period_months=period_months
        )
        return result

    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export attendance data",
    description="Export attendance data in various formats (CSV, Excel, PDF).",
    responses={
        200: {"description": "File download initiated"},
        400: {"description": "Invalid export parameters"},
    },
)
async def export_my_attendance(
    format: str = Query(
        "csv",
        regex="^(csv|excel|pdf)$",
        description="Export format: csv, excel, or pdf"
    ),
    start_date: Optional[date] = Query(
        None,
        description="Start date for export"
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for export"
    ),
    include_summary: bool = Query(
        True,
        description="Include summary statistics"
    ),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
):
    """
    Export attendance data in specified format.
    
    Args:
        format: Export format (csv, excel, pdf)
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_summary: Whether to include summary
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        File download response
    """
    try:
        # Validate date range
        if start_date and end_date and end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End date must be after or equal to start date"
            )

        result = await attendance_service.export_student_attendance(
            student_id=current_user.id,
            format=format,
            start_date=start_date,
            end_date=end_date,
            include_summary=include_summary
        )
        
        # Return file response (implementation depends on your file handling strategy)
        return result

    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )