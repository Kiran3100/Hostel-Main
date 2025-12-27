"""
Booking Calendar API

Provides calendar and availability views including:
- Monthly booking calendar
- Availability calendar with room/bed counts
- Date range availability queries
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.booking.booking_calendar import AvailabilityCalendar, CalendarView
from app.services.booking.booking_calendar_service import BookingCalendarService

logger = get_logger(__name__)

router = APIRouter(prefix="/bookings/calendar", tags=["bookings:calendar"])


def get_calendar_service(
    db: Session = Depends(deps.get_db),
) -> BookingCalendarService:
    """
    Dependency injection for BookingCalendarService.
    
    Args:
        db: Database session
        
    Returns:
        BookingCalendarService instance
    """
    return BookingCalendarService(db=db)


@router.get(
    "/month",
    response_model=CalendarView,
    summary="Get monthly booking calendar",
    description="Retrieve a calendar view of bookings for a specific month.",
    responses={
        200: {"description": "Calendar retrieved successfully"},
        400: {"description": "Invalid month or year"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    },
)
async def get_month_view(
    hostel_id: str = Query(..., description="Hostel unique identifier"),
    year: int = Query(..., ge=2000, le=2100, description="Year (e.g., 2024)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    admin=Depends(deps.get_admin_user),
    service: BookingCalendarService = Depends(get_calendar_service),
) -> CalendarView:
    """
    Get monthly booking calendar view.
    
    Args:
        hostel_id: Unique hostel identifier
        year: Calendar year
        month: Calendar month (1-12)
        admin: Admin user requesting the calendar
        service: Calendar service instance
        
    Returns:
        Calendar view with bookings for the month
        
    Raises:
        HTTPException: If retrieval fails or invalid date
    """
    try:
        # Validate date
        try:
            date(year, month, 1)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid year/month combination: {year}-{month}",
            )
        
        logger.debug(
            f"Fetching calendar for hostel {hostel_id}, {year}-{month:02d}",
            extra={"hostel_id": hostel_id, "year": year, "month": month},
        )
        
        calendar_view = service.get_month_view(hostel_id, year, month)
        
        return calendar_view
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching calendar for hostel {hostel_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve calendar",
        )


@router.get(
    "/availability",
    response_model=AvailabilityCalendar,
    summary="Get availability calendar",
    description="Retrieve room/bed availability for a date range.",
    responses={
        200: {"description": "Availability calendar retrieved successfully"},
        400: {"description": "Invalid date range"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    },
)
async def get_availability_calendar(
    hostel_id: str = Query(..., description="Hostel unique identifier"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    room_type: str = Query(None, description="Optional room type filter"),
    admin=Depends(deps.get_admin_user),
    service: BookingCalendarService = Depends(get_calendar_service),
) -> AvailabilityCalendar:
    """
    Get availability calendar for a date range.
    
    Args:
        hostel_id: Unique hostel identifier
        start_date: Range start date (YYYY-MM-DD format)
        end_date: Range end date (YYYY-MM-DD format)
        room_type: Optional room type filter
        admin: Admin user requesting availability
        service: Calendar service instance
        
    Returns:
        Availability calendar with daily counts
        
    Raises:
        HTTPException: If retrieval fails or invalid dates
    """
    try:
        # Validate dates
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            
            if start > end:
                raise ValueError("Start date must be before or equal to end date")
                
            # Limit date range to prevent performance issues
            if (end - start).days > 365:
                raise ValueError("Date range cannot exceed 365 days")
                
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date range: {str(e)}",
            )
        
        logger.debug(
            f"Fetching availability for hostel {hostel_id}, {start_date} to {end_date}",
            extra={
                "hostel_id": hostel_id,
                "start_date": start_date,
                "end_date": end_date,
                "room_type": room_type,
            },
        )
        
        availability = service.get_availability_calendar(
            hostel_id, start_date, end_date, room_type=room_type
        )
        
        return availability
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching availability for hostel {hostel_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve availability calendar",
        )


@router.get(
    "/occupancy/{hostel_id}",
    summary="Get occupancy statistics",
    description="Get current and historical occupancy rates for a hostel.",
    responses={
        200: {"description": "Occupancy statistics retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    },
)
async def get_occupancy_stats(
    hostel_id: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    admin=Depends(deps.get_admin_user),
    service: BookingCalendarService = Depends(get_calendar_service),
) -> Any:
    """
    Get occupancy statistics for a date range.
    
    Args:
        hostel_id: Unique hostel identifier
        start_date: Range start date
        end_date: Range end date
        admin: Admin user requesting statistics
        service: Calendar service instance
        
    Returns:
        Occupancy statistics and trends
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(f"Fetching occupancy stats for hostel {hostel_id}")
        
        stats = service.get_occupancy_stats(hostel_id, start_date, end_date)
        
        return stats
    except Exception as e:
        logger.error(
            f"Error fetching occupancy stats for hostel {hostel_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve occupancy statistics",
        )