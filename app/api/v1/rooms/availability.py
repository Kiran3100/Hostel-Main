"""
Room Availability Endpoints

Provides endpoints for checking room availability, calendar views, and forecasting.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.room.room_availability_service import RoomAvailabilityService
from app.schemas.room import (
    AvailabilityCalendar,
    AvailabilityResponse,
    RoomAvailabilityRequest,
)

router = APIRouter(
    prefix="/rooms/availability",
    tags=["Rooms - Availability"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_availability_service() -> RoomAvailabilityService:
    """
    Dependency provider for RoomAvailabilityService.
    
    Raises:
        NotImplementedError: Must be overridden in dependency configuration
    """
    raise NotImplementedError(
        "RoomAvailabilityService dependency must be configured. "
        "Override get_availability_service in your dependency injection configuration."
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract and validate current authenticated user.
    
    Note: This dependency is optional for public availability checking.
    Override as needed for your authentication requirements.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        Current authenticated user object or None for public access
    """
    return auth.get_current_user()


# ============================================================================
# Availability Checking Endpoints
# ============================================================================

@router.post(
    "/check",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Check room availability",
    description="Check availability for specific dates, hostel, and room types",
    response_description="Availability results with matching rooms",
)
async def check_availability(
    payload: RoomAvailabilityRequest,
    availability_service: RoomAvailabilityService = Depends(get_availability_service),
    # Optional auth for public access - remove Depends(get_current_user) if needed
) -> AvailabilityResponse:
    """
    Check room availability based on specified criteria.
    
    Searches for available rooms matching the given parameters:
    - Date range (check-in and check-out)
    - Hostel or location
    - Room type preferences
    - Number of guests
    - Additional filters
    
    This endpoint can be made public for guest searches or
    require authentication for internal use.
    
    Args:
        payload: Availability search criteria
        availability_service: Injected availability service
        
    Returns:
        Available rooms matching the criteria with pricing and details
        
    Raises:
        HTTPException: If search fails or invalid date range provided
    """
    result = availability_service.check_availability(criteria=payload)
    return result.unwrap()


@router.get(
    "/calendar/{room_id}",
    response_model=AvailabilityCalendar,
    summary="Get availability calendar",
    description="Get monthly availability calendar for a specific room",
    response_description="Calendar view showing availability for each day",
)
async def get_availability_calendar(
    room_id: str = Path(
        ..., 
        description="Unique identifier of the room",
        min_length=1,
    ),
    month: str = Query(
        ..., 
        description="Month in YYYY-MM format (e.g., 2024-03)",
        regex=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    availability_service: RoomAvailabilityService = Depends(get_availability_service),
    current_user: Any = Depends(get_current_user),
) -> AvailabilityCalendar:
    """
    Get availability calendar for a specific room and month.
    
    Returns a calendar view showing:
    - Available dates
    - Booked/occupied dates
    - Blocked/maintenance dates
    - Pricing for each date (if applicable)
    
    Useful for displaying interactive booking calendars.
    
    Args:
        room_id: Room identifier
        month: Target month in YYYY-MM format
        availability_service: Injected availability service
        current_user: Authenticated user
        
    Returns:
        Calendar data structure with daily availability
        
    Raises:
        HTTPException: If room not found or invalid month format
    """
    result = availability_service.get_availability_calendar(
        room_id=room_id, 
        month=month,
    )
    return result.unwrap()


@router.get(
    "/forecast",
    summary="Get availability forecast",
    description="Get availability forecast for a hostel over a specified period",
    response_description="Forecasted availability metrics and trends",
)
async def get_availability_forecast(
    hostel_id: str = Query(
        ..., 
        description="Hostel identifier",
        min_length=1,
    ),
    days: int = Query(
        30, 
        ge=7, 
        le=90, 
        description="Number of days to forecast (7-90 days)",
    ),
    availability_service: RoomAvailabilityService = Depends(get_availability_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Get availability forecast for a hostel.
    
    Provides predictive availability data for capacity planning:
    - Daily availability projections
    - Occupancy trends
    - Peak periods identification
    - Capacity utilization forecasts
    
    Useful for management dashboards and resource planning.
    
    Args:
        hostel_id: Hostel identifier
        days: Forecast period in days (minimum 7, maximum 90)
        availability_service: Injected availability service
        current_user: Authenticated user
        
    Returns:
        Forecast data with daily projections and analytics
        
    Raises:
        HTTPException: If hostel not found or invalid parameters
    """
    result = availability_service.get_availability_forecast(
        hostel_id=hostel_id, 
        days=days,
    )
    return result.unwrap()