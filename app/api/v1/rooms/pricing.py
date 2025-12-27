"""
Room Pricing Management Endpoints

Provides endpoints for dynamic pricing management, bulk updates, and pricing analytics.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, Body, status

from app.core.dependencies import AuthenticationDependency
from app.services.room.room_pricing_service import RoomPricingService

router = APIRouter(
    prefix="/rooms/pricing",
    tags=["Rooms - Pricing"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_pricing_service() -> RoomPricingService:
    """
    Dependency provider for RoomPricingService.
    
    Raises:
        NotImplementedError: Must be overridden in dependency configuration
    """
    raise NotImplementedError(
        "RoomPricingService dependency must be configured. "
        "Override get_pricing_service in your dependency injection configuration."
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract and validate current authenticated user.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        Current authenticated user object
    """
    return auth.get_current_user()


# ============================================================================
# Pricing Management Endpoints
# ============================================================================

@router.post(
    "/update",
    status_code=status.HTTP_200_OK,
    summary="Update room pricing",
    description="Update pricing for a specific room with effective date",
    response_description="Pricing update confirmation",
)
async def update_pricing(
    room_id: str = Query(
        ..., 
        description="Room identifier",
        min_length=1,
    ),
    price: float = Query(
        ..., 
        ge=0, 
        description="New price (must be non-negative)",
    ),
    effective_from: str = Query(
        ..., 
        description="Effective date in ISO format (YYYY-MM-DD)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    pricing_service: RoomPricingService = Depends(get_pricing_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Update pricing for a specific room.
    
    Creates a new pricing record with an effective date, allowing
    for scheduled price changes. Historical pricing is preserved.
    
    Features:
    - Date-based pricing activation
    - Maintains pricing history
    - Supports future-dated price changes
    
    Args:
        room_id: Room identifier
        price: New price amount (non-negative)
        effective_from: Date when new price becomes effective (YYYY-MM-DD)
        pricing_service: Injected pricing service
        current_user: Authenticated user
        
    Returns:
        Confirmation with updated pricing details
        
    Raises:
        HTTPException: If room not found or invalid price/date
    """
    result = pricing_service.update_room_pricing(
        room_id=room_id,
        price=price,
        effective_from=effective_from,
    )
    return result.unwrap()


@router.post(
    "/bulk-update",
    status_code=status.HTTP_200_OK,
    summary="Bulk update room pricing",
    description="Update pricing for multiple rooms simultaneously",
    response_description="Bulk update confirmation with affected count",
)
async def bulk_update_pricing(
    room_ids: List[str] = Body(
        ..., 
        description="List of room identifiers",
        min_items=1,
    ),
    price: float = Body(
        ..., 
        ge=0, 
        description="New price for all rooms",
    ),
    effective_from: str = Body(
        ..., 
        description="Effective date in ISO format (YYYY-MM-DD)",
    ),
    pricing_service: RoomPricingService = Depends(get_pricing_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Update pricing for multiple rooms in a single operation.
    
    Efficiently applies the same pricing change to multiple rooms.
    Useful for seasonal pricing adjustments or category-wide updates.
    
    The operation is atomic - either all updates succeed or none do.
    
    Args:
        room_ids: List of room identifiers to update
        price: New price to apply to all rooms
        effective_from: Effective date for the price change
        pricing_service: Injected pricing service
        current_user: Authenticated user
        
    Returns:
        Confirmation with count of updated rooms
        
    Raises:
        HTTPException: If any room not found or operation fails
    """
    result = pricing_service.bulk_update_room_pricing(
        room_ids=room_ids,
        price=price,
        effective_from=effective_from,
    )
    return result.unwrap()


# ============================================================================
# Pricing History and Analytics
# ============================================================================

@router.get(
    "/history",
    summary="Get pricing history",
    description="Retrieve complete pricing history for a specific room",
    response_description="Chronological list of pricing changes",
)
async def get_pricing_history(
    room_id: str = Query(
        ..., 
        description="Room identifier",
        min_length=1,
    ),
    pricing_service: RoomPricingService = Depends(get_pricing_service),
    current_user: Any = Depends(get_current_user),
) -> list:
    """
    Get complete pricing history for a room.
    
    Returns all historical pricing records in chronological order,
    including:
    - Price amount
    - Effective date
    - Change timestamp
    - Modified by (user)
    
    Useful for auditing and pricing trend analysis.
    
    Args:
        room_id: Room identifier
        pricing_service: Injected pricing service
        current_user: Authenticated user
        
    Returns:
        List of pricing history records
        
    Raises:
        HTTPException: If room not found
    """
    result = pricing_service.get_pricing_history(room_id=room_id)
    return result.unwrap()


@router.get(
    "/analytics",
    summary="Get pricing analytics",
    description="Get pricing analytics and insights for a hostel",
    response_description="Pricing statistics and trends",
)
async def get_pricing_analytics(
    hostel_id: str = Query(
        ..., 
        description="Hostel identifier",
        min_length=1,
    ),
    start_date: str = Query(
        ..., 
        description="Analysis start date (YYYY-MM-DD)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    end_date: str = Query(
        ..., 
        description="Analysis end date (YYYY-MM-DD)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    pricing_service: RoomPricingService = Depends(get_pricing_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Get pricing analytics for a hostel over a specified period.
    
    Provides comprehensive pricing insights:
    - Average pricing by room type
    - Price distribution and ranges
    - Pricing trends over time
    - Revenue impact analysis
    - Competitive positioning metrics
    
    Useful for revenue management and pricing optimization.
    
    Args:
        hostel_id: Hostel identifier
        start_date: Analysis period start (YYYY-MM-DD)
        end_date: Analysis period end (YYYY-MM-DD)
        pricing_service: Injected pricing service
        current_user: Authenticated user
        
    Returns:
        Analytics data with metrics and trends
        
    Raises:
        HTTPException: If hostel not found or invalid date range
    """
    result = pricing_service.get_pricing_analytics(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
    )
    return result.unwrap()