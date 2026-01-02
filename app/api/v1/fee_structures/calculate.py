"""
Fee Calculation and Projection Endpoints

This module handles all fee-related calculations including:
- Quote generation for prospective bookings
- Fee calculations for existing bookings
- Revenue projections for hostels
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.fee_structure import (
    FeeCalculation,
    FeeProjection,
    FeeQuoteRequest,
)
from app.services.fee_structure.fee_calculation_service import FeeCalculationService
from app.services.fee_structure.fee_projection_service import FeeProjectionService

# Router configuration with prefix and tags
router = APIRouter(
    prefix="/fee-structures/calculate",
    tags=["fee-structures:calculate"]
)


# Dependency injection for services
def get_calculation_service(
    db: Session = Depends(deps.get_db)
) -> FeeCalculationService:
    """
    Dependency provider for FeeCalculationService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        FeeCalculationService: Initialized service instance
    """
    return FeeCalculationService(db=db)


def get_projection_service(
    db: Session = Depends(deps.get_db)
) -> FeeProjectionService:
    """
    Dependency provider for FeeProjectionService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        FeeProjectionService: Initialized service instance
    """
    return FeeProjectionService(db=db)


@router.post(
    "/quote",
    response_model=FeeCalculation,
    status_code=status.HTTP_200_OK,
    summary="Calculate fee quote without persisting",
    description="""
    Generate a fee calculation based on room type, dates, and optional discount codes.
    This endpoint does not save the calculation to the database.
    
    **Use Cases:**
    - Prospective customer inquiries
    - Booking form price previews
    - Marketing campaign calculations
    
    **Request Body:**
    - hostel_id: UUID of the hostel
    - room_type: Type of room (SINGLE, DOUBLE, TRIPLE, etc.)
    - check_in_date: Proposed check-in date
    - check_out_date: Proposed check-out date
    - number_of_guests: Number of guests (default: 1)
    - discount_code: Optional promo/discount code
    - include_mess: Override mess inclusion
    - student_id: Optional student ID for personalized pricing
    """,
    responses={
        200: {
            "description": "Fee calculation successful",
            "model": FeeCalculation
        },
        400: {
            "description": "Invalid request parameters"
        },
        404: {
            "description": "Room type or discount code not found"
        },
        422: {
            "description": "Validation error"
        }
    }
)
def calculate_quote(
    payload: FeeQuoteRequest,
    service: FeeCalculationService = Depends(get_calculation_service),
) -> Any:
    """
    Calculate fees for a potential booking without saving to database.
    
    Args:
        payload: Quote request containing room type, dates, and optional discount
        service: Fee calculation service instance
        
    Returns:
        FeeCalculation: Detailed breakdown of calculated fees
        
    Raises:
        HTTPException: If calculation fails due to invalid data
    """
    try:
        return service.calculate_quote(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        # Log the error for debugging
        # logger.error(f"Quote calculation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate quote. Please try again later."
        )


@router.get(
    "/booking/{booking_id}",
    response_model=FeeCalculation,
    status_code=status.HTTP_200_OK,
    summary="Retrieve fee calculation for existing booking",
    description="""
    Fetch the complete fee breakdown for a specific booking.
    Requires authentication and booking ownership or admin privileges.
    
    **Authorization:**
    - Students can view their own bookings
    - Admins can view any booking
    """,
    responses={
        200: {
            "description": "Fee calculation retrieved successfully",
            "model": FeeCalculation
        },
        401: {
            "description": "Unauthorized - Authentication required"
        },
        403: {
            "description": "Forbidden - Insufficient permissions"
        },
        404: {
            "description": "Booking not found"
        }
    }
)
def get_booking_fees(
    booking_id: UUID,
    current_user=Depends(deps.get_current_user),
    service: FeeCalculationService = Depends(get_calculation_service),
) -> Any:
    """
    Get detailed fee calculation for a specific booking.
    
    Args:
        booking_id: Unique identifier of the booking
        current_user: Authenticated user from dependency injection
        service: Fee calculation service instance
        
    Returns:
        FeeCalculation: Complete fee breakdown for the booking
        
    Raises:
        HTTPException: If booking not found or user lacks permission
    """
    try:
        fee_calculation = service.get_calculations_for_booking(
            booking_id=booking_id,
            user_id=current_user.id
        )
        
        if not fee_calculation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fee calculation not found for booking: {booking_id}"
            )
        
        return fee_calculation
        
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        # logger.error(f"Failed to retrieve booking fees: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve booking fees"
        )


@router.get(
    "/projections",
    response_model=FeeProjection,
    status_code=status.HTTP_200_OK,
    summary="Generate revenue projections for hostel",
    description="""
    Calculate projected revenue for a hostel over a specified time period.
    Requires administrative privileges.
    
    **Features:**
    - Configurable projection period (1-60 months)
    - Historical data analysis (optional)
    - Seasonal trend consideration
    - Occupancy rate projections
    - Monthly breakdown of revenue streams
    
    **Query Parameters:**
    - hostel_id: UUID of the hostel
    - months: Number of months to project (1-60, default: 12)
    - include_historical: Include historical comparison (default: true)
    """,
    responses={
        200: {
            "description": "Projections calculated successfully",
            "model": FeeProjection
        },
        401: {
            "description": "Unauthorized - Admin access required"
        },
        404: {
            "description": "Hostel not found"
        },
        422: {
            "description": "Invalid query parameters"
        }
    }
)
def get_fee_projections(
    hostel_id: UUID = Query(
        ...,
        description="Unique identifier of the hostel"
    ),
    months: int = Query(
        default=12,
        ge=1,
        le=60,
        description="Number of months to project (1-60)"
    ),
    include_historical: bool = Query(
        default=True,
        description="Include historical data in response"
    ),
    _admin=Depends(deps.get_admin_user),
    service: FeeProjectionService = Depends(get_projection_service),
) -> Any:
    """
    Generate revenue projections for a specific hostel.
    
    Args:
        hostel_id: Unique identifier of the hostel
        months: Number of months to project (1-60)
        include_historical: Whether to include historical data
        _admin: Authenticated admin user
        service: Fee projection service instance
        
    Returns:
        FeeProjection: Detailed revenue projections with breakdowns
        
    Raises:
        HTTPException: If hostel not found or projection fails
    """
    try:
        projection = service.project_for_hostel(
            hostel_id=hostel_id,
            months=months,
            include_historical=include_historical
        )
        
        if not projection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hostel not found: {hostel_id}"
            )
        
        return projection
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        # logger.error(f"Failed to generate projections: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate projections. Please try again later."
        )