"""
Hostel Comparison API Endpoints
Provides functionality to compare multiple hostels and get recommendations
"""
from typing import Any, List, Dict
from enum import Enum
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_comparison import (
    HostelComparisonRequest,
    ComparisonResult,
    ComparisonSummary,
    ComparisonCriteria,
    HostelRecommendation,
    PricingComparison,
)
from app.services.hostel.hostel_comparison_service import HostelComparisonService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/hostels/comparison", tags=["hostels:comparison"])


def get_comparison_service(
    db: Session = Depends(deps.get_db)
) -> HostelComparisonService:
    """
    Dependency to get hostel comparison service instance
    
    Args:
        db: Database session
        
    Returns:
        HostelComparisonService instance
    """
    return HostelComparisonService(db=db)


@router.post(
    "",
    response_model=ComparisonResult,
    summary="Compare multiple hostels",
    description="Compare 2-4 hostels side by side across multiple criteria",
    responses={
        200: {"description": "Comparison completed successfully"},
        400: {"description": "Invalid number of hostels or invalid hostel IDs"},
        404: {"description": "One or more hostels not found"},
    },
)
def compare_hostels(
    payload: HostelComparisonRequest,
    service: HostelComparisonService = Depends(get_comparison_service),
) -> ComparisonResult:
    """
    Compare multiple hostels side by side.
    
    Compares hostels across:
    - Pricing
    - Amenities
    - Location & accessibility
    - Reviews & ratings
    - Room types & availability
    - Policies
    
    Args:
        payload: Comparison request with hostel IDs and criteria
        service: Comparison service instance
        
    Returns:
        Detailed comparison result
        
    Raises:
        HTTPException: If validation fails or hostels not found
    """
    try:
        logger.info(
            f"Comparing {len(payload.hostel_ids)} hostels: {payload.hostel_ids}"
        )
        
        comparison = service.compare(
            hostel_ids=payload.hostel_ids,
            criteria=payload.criteria
        )
        
        if not comparison:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more hostels not found"
            )
        
        logger.info("Comparison completed successfully")
        return comparison
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error comparing hostels: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare hostels"
        )


@router.get(
    "/pricing",
    response_model=List[PricingComparison],
    summary="Compare pricing across hostels",
    description="Get detailed pricing comparison for multiple hostels",
    responses={
        200: {"description": "Pricing comparison retrieved successfully"},
        400: {"description": "Invalid parameters"},
        404: {"description": "One or more hostels not found"},
    },
)
def compare_pricing(
    hostel_ids: List[UUID] = Query(
        ...,
        min_length=2,
        max_length=4,
        description="List of hostel IDs to compare (2-4 hostels)"
    ),
    room_type: str | None = Query(
        None,
        description="Filter by specific room type"
    ),
    duration: int = Query(
        1,
        description="Booking duration in months",
        ge=1,
        le=12
    ),
    service: HostelComparisonService = Depends(get_comparison_service),
) -> List[PricingComparison]:
    """
    Compare pricing across multiple hostels.
    
    Provides:
    - Base rent
    - Additional fees
    - Discounts
    - Total cost calculations
    - Price per amenity
    
    Args:
        hostel_ids: List of hostel identifiers (2-4 hostels)
        room_type: Optional room type filter
        duration: Booking duration in months
        service: Comparison service instance
        
    Returns:
        List of pricing comparisons
        
    Raises:
        HTTPException: If validation fails or retrieval fails
    """
    try:
        logger.info(f"Comparing pricing for hostels: {hostel_ids}")
        
        pricing = service.compare_pricing(
            hostel_ids=hostel_ids,
            room_type=room_type,
            duration=duration
        )
        
        if not pricing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pricing data found for the specified hostels"
            )
        
        logger.info("Pricing comparison completed successfully")
        return pricing
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error comparing pricing: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare pricing"
        )


@router.get(
    "/recommendations",
    response_model=List[HostelRecommendation],
    summary="Get hostel recommendations",
    description="Get personalized hostel recommendations based on criteria",
    responses={
        200: {"description": "Recommendations retrieved successfully"},
        400: {"description": "Invalid search criteria"},
    },
)
def get_recommendations(
    city: str = Query(
        ...,
        description="City to search in",
        min_length=1
    ),
    budget_min: float | None = Query(
        None,
        description="Minimum budget",
        ge=0
    ),
    budget_max: float | None = Query(
        None,
        description="Maximum budget",
        ge=0
    ),
    room_type: str | None = Query(
        None,
        description="Preferred room type"
    ),
    amenities: List[str] | None = Query(
        None,
        description="Required amenities"
    ),
    gender_preference: str | None = Query(
        None,
        description="Gender preference (male, female, co-ed)",
        pattern="^(male|female|co-ed)$"
    ),
    distance_from_university: float | None = Query(
        None,
        description="Maximum distance from university in km",
        ge=0,
        le=50
    ),
    sort_by: str = Query(
        "recommended",
        description="Sort recommendations by",
        pattern="^(recommended|price_low|price_high|rating|distance)$"
    ),
    limit: int = Query(
        10,
        description="Maximum number of recommendations",
        ge=1,
        le=50
    ),
    current_user=Depends(deps.get_current_user_optional),
    service: HostelComparisonService = Depends(get_comparison_service),
) -> List[HostelRecommendation]:
    """
    Get personalized hostel recommendations.
    
    Uses machine learning and filtering to provide:
    - Best matches based on criteria
    - Similar to previously viewed hostels
    - Popular hostels in the area
    - Best value hostels
    
    Args:
        city: City to search in
        budget_min: Minimum budget constraint
        budget_max: Maximum budget constraint
        room_type: Preferred room type
        amenities: List of required amenities
        gender_preference: Gender preference for hostel
        distance_from_university: Maximum distance from university
        sort_by: Sorting preference
        limit: Maximum number of results
        current_user: Optional current user for personalization
        service: Comparison service instance
        
    Returns:
        List of hostel recommendations
        
    Raises:
        HTTPException: If search fails
    """
    try:
        # Validate budget range
        if budget_min and budget_max and budget_min > budget_max:
            raise ValueError("budget_min must be less than budget_max")
        
        logger.info(
            f"Getting recommendations for city: {city} "
            f"with budget range: {budget_min}-{budget_max}"
        )
        
        criteria = ComparisonCriteria(
            city=city,
            budget_min=budget_min,
            budget_max=budget_max,
            room_type=room_type,
            amenities=amenities or [],
            gender_preference=gender_preference,
            distance_from_university=distance_from_university
        )
        
        recommendations = service.get_recommendations(
            criteria=criteria,
            user_id=current_user.id if current_user else None,
            sort_by=sort_by,
            limit=limit
        )
        
        logger.info(f"Found {len(recommendations)} recommendations")
        return recommendations
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recommendations"
        )


@router.get(
    "/summary",
    response_model=ComparisonSummary,
    summary="Get quick comparison summary",
    description="Get a quick summary comparison of multiple hostels",
    responses={
        200: {"description": "Summary retrieved successfully"},
        400: {"description": "Invalid parameters"},
    },
)
def get_comparison_summary(
    hostel_ids: List[UUID] = Query(
        ...,
        min_length=2,
        max_length=4,
        description="List of hostel IDs to compare"
    ),
    service: HostelComparisonService = Depends(get_comparison_service),
) -> ComparisonSummary:
    """
    Get a quick comparison summary.
    
    Provides high-level overview without detailed breakdowns:
    - Price ranges
    - Average ratings
    - Key features
    - Availability status
    
    Args:
        hostel_ids: List of hostel identifiers
        service: Comparison service instance
        
    Returns:
        Comparison summary
    """
    try:
        logger.info(f"Getting comparison summary for: {hostel_ids}")
        
        summary = service.get_summary(hostel_ids)
        
        return summary
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get comparison summary"
        )