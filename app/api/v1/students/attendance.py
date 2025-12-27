"""
Student Attendance API Endpoints

Provides endpoints for students to view their attendance history and records.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import Field

from app.core.dependencies import AuthenticationDependency, get_current_user
from app.services.attendance.attendance_service import AttendanceService
from app.schemas.attendance import AttendanceRecord, AttendanceResponse
from app.schemas.base import User

router = APIRouter(
    prefix="/students/me/attendance",
    tags=["Students - Attendance"],
)


def get_attendance_service() -> AttendanceService:
    """
    Dependency injection for AttendanceService.
    
    Returns:
        AttendanceService: Instance of the attendance service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("AttendanceService dependency not configured")


@router.get(
    "",
    response_model=AttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get my attendance history",
    description="Retrieve attendance records for the currently authenticated student within an optional date range.",
    responses={
        200: {"description": "Attendance records retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        422: {"description": "Validation error - Invalid date format"},
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
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: User = Depends(get_current_user),
) -> AttendanceResponse:
    """
    Get attendance history for the authenticated student.
    
    Args:
        start_date: Optional start date for filtering records
        end_date: Optional end date for filtering records
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        AttendanceResponse: List of attendance records with metadata
        
    Raises:
        HTTPException: If retrieval fails or user lacks permissions
    """
    result = attendance_service.get_student_attendance(
        student_id=current_user.id,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
    )
    return result.unwrap()


@router.get(
    "/summary",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get my attendance summary statistics",
    description="Retrieve aggregated attendance statistics for the authenticated student.",
)
async def get_my_attendance_summary(
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
) -> dict:
    """
    Get attendance summary with statistics like present/absent counts and percentage.
    
    Args:
        month: Optional month filter
        year: Optional year filter
        attendance_service: Injected attendance service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Attendance summary with counts and percentages
    """
    result = attendance_service.get_attendance_summary(
        student_id=current_user.id,
        month=month,
        year=year,
    )
    return result.unwrap()