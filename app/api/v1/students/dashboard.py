"""
Student Dashboard API Endpoints

Provides aggregated dashboard data for student view.
"""
from typing import Any

from fastapi import APIRouter, Depends, status, Query
from datetime import date

from app.core.dependencies import get_current_user
from app.services.student.student_aggregate_service import StudentAggregateService
from app.schemas.student_dashboard import (
    StudentDashboard,
    DashboardPeriod,
)
from app.schemas.base import User

router = APIRouter(
    prefix="/students/me/dashboard",
    tags=["Students - Dashboard"],
)


def get_aggregate_service() -> StudentAggregateService:
    """
    Dependency injection for StudentAggregateService.
    
    Returns:
        StudentAggregateService: Instance of the aggregate service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("StudentAggregateService dependency not configured")


@router.get(
    "",
    response_model=StudentDashboard,
    status_code=status.HTTP_200_OK,
    summary="Get student dashboard",
    description="Retrieve aggregated dashboard data including attendance, payments, complaints, and leave statistics.",
    responses={
        200: {"description": "Dashboard data retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
    },
)
async def get_dashboard(
    period: DashboardPeriod = Query(
        DashboardPeriod.CURRENT_MONTH,
        description="Time period for dashboard statistics",
    ),
    aggregate_service: StudentAggregateService = Depends(get_aggregate_service),
    current_user: User = Depends(get_current_user),
) -> StudentDashboard:
    """
    Returns aggregated dashboard data for the currently logged-in student.
    
    Includes:
    - Attendance summary and recent records
    - Payment status and pending dues
    - Active complaints count
    - Leave balance and pending applications
    - Recent notifications
    - Room and hostel information
    
    Args:
        period: Time period filter for statistics
        aggregate_service: Injected aggregate service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentDashboard: Comprehensive dashboard data
    """
    result = aggregate_service.get_student_dashboard_stats(
        student_id=current_user.id,
        period=period,
    )
    return result.unwrap()


@router.get(
    "/quick-stats",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get quick dashboard statistics",
    description="Retrieve lightweight dashboard statistics for quick loading.",
)
async def get_quick_stats(
    aggregate_service: StudentAggregateService = Depends(get_aggregate_service),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get quick statistics for faster dashboard loading.
    
    Returns minimal essential data:
    - Unread notifications count
    - Pending dues amount
    - Today's attendance status
    - Pending leave applications
    
    Args:
        aggregate_service: Injected aggregate service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Quick statistics data
    """
    result = aggregate_service.get_quick_stats(student_id=current_user.id)
    return result.unwrap()