"""
Public Hostel API Endpoints
Unauthenticated endpoints for public hostel information
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_public import (
    PublicHostelProfile,
    PublicHostelListItem,
    PublicHostelSearch,
)
from app.services.hostel.hostel_service import HostelService
from app.schemas.common import PaginatedResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/hostels/public", tags=["hostels:public"])


def get_hostel_service(db: Session = Depends(deps.get_db)) -> HostelService:
    """
    Dependency to get hostel service instance
    
    Args:
        db: Database session
        
    Returns:
        HostelService instance
    """
    return HostelService(db=db)


@router.get(
    "/{slug}",
    response_model=PublicHostelProfile,
    summary="Get public hostel profile by slug",
    description="Retrieve public information about a hostel using its URL slug",
    responses={
        200: {"description": "Hostel profile retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
def get_public_hostel(
    slug: str = Path(
        ...,
        description="URL-friendly slug of the hostel",
        example="grand-valley-hostel-mumbai"
    ),
    service: HostelService = Depends(get_hostel_service),
) -> PublicHostelProfile:
    """
    Get public hostel profile by slug.
    
    Returns publicly accessible information including:
    - Basic details
    - Location
    - Amenities
    - Room types and pricing
    - Reviews and ratings
    - Photos and media
    
    Does NOT include:
    - Internal statistics
    - Admin information
    - Student personal data
    - Financial details
    
    Args:
        slug: The hostel's URL slug
        service: Hostel service instance
        
    Returns:
        Public hostel profile
        
    Raises:
        HTTPException: If hostel not found or not publicly visible
    """
    try:
        hostel = service.get_by_slug(slug, public_only=True)
        
        if not hostel:
            logger.warning(f"Hostel not found for slug: {slug}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        # Check if hostel is publicly visible
        if not hostel.is_active or hostel.is_archived:
            logger.warning(f"Attempted access to inactive hostel: {slug}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not available"
            )
        
        logger.info(f"Public profile accessed for hostel: {slug}")
        return hostel
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving public hostel: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hostel information"
        )


@router.get(
    "",
    response_model=PaginatedResponse[PublicHostelListItem],
    summary="Search public hostels",
    description="Search and filter publicly available hostels",
    responses={
        200: {"description": "Search results retrieved successfully"},
        400: {"description": "Invalid search parameters"},
    },
)
def search_public_hostels(
    city: str | None = Query(
        None,
        description="Filter by city",
        min_length=2
    ),
    search: str | None = Query(
        None,
        description="Search term (name, description, location)",
        min_length=2
    ),
    min_price: float | None = Query(
        None,
        description="Minimum price per month",
        ge=0
    ),
    max_price: float | None = Query(
        None,
        description="Maximum price per month",
        ge=0
    ),
    room_type: str | None = Query(
        None,
        description="Filter by room type"
    ),
    gender: str | None = Query(
        None,
        description="Filter by gender preference",
        regex="^(male|female|co-ed)$"
    ),
    amenities: List[str] | None = Query(
        None,
        description="Required amenities"
    ),
    min_rating: float | None = Query(
        None,
        description="Minimum average rating",
        ge=0,
        le=5
    ),
    sort_by: str = Query(
        "featured",
        description="Sort by",
        regex="^(featured|price_low|price_high|rating|newest|closest)$"
    ),
    page: int = Query(1, description="Page number", ge=1),
    page_size: int = Query(20, description="Items per page", ge=1, le=100),
    service: HostelService = Depends(get_hostel_service),
) -> PaginatedResponse[PublicHostelListItem]:
    """
    Search publicly available hostels.
    
    Supports comprehensive filtering and sorting options.
    
    Args:
        city: City filter
        search: Text search across multiple fields
        min_price: Minimum price filter
        max_price: Maximum price filter
        room_type: Room type filter
        gender: Gender preference filter
        amenities: Required amenities list
        min_rating: Minimum rating filter
        sort_by: Sort order
        page: Page number
        page_size: Results per page
        service: Hostel service instance
        
    Returns:
        Paginated search results
        
    Raises:
        HTTPException: If search fails
    """
    try:
        # Validate price range
        if min_price and max_price and min_price > max_price:
            raise ValueError("min_price must be less than max_price")
        
        search_params = PublicHostelSearch(
            city=city,
            search=search,
            min_price=min_price,
            max_price=max_price,
            room_type=room_type,
            gender=gender,
            amenities=amenities or [],
            min_rating=min_rating,
            sort_by=sort_by,
            page=page,
            page_size=page_size
        )
        
        logger.info(f"Public hostel search: {search_params.dict(exclude_unset=True)}")
        
        results = service.search_public(search_params)
        
        logger.info(
            f"Found {results.total} hostels "
            f"(returning page {page} with {len(results.items)} items)"
        )
        return results
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error searching hostels: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search hostels"
        )


@router.get(
    "/featured/list",
    response_model=List[PublicHostelListItem],
    summary="Get featured hostels",
    description="Retrieve a list of featured/recommended hostels",
    responses={
        200: {"description": "Featured hostels retrieved successfully"},
    },
)
def get_featured_hostels(
    city: str | None = Query(None, description="Filter by city"),
    limit: int = Query(10, description="Number of results", ge=1, le=50),
    service: HostelService = Depends(get_hostel_service),
) -> List[PublicHostelListItem]:
    """
    Get featured hostels.
    
    Returns hostels marked as featured, typically:
    - Premium listings
    - Highly rated hostels
    - Recently verified
    - Promotional partnerships
    
    Args:
        city: Optional city filter
        limit: Maximum number of results
        service: Hostel service instance
        
    Returns:
        List of featured hostels
    """
    try:
        featured = service.get_featured(city=city, limit=limit)
        
        logger.info(f"Retrieved {len(featured)} featured hostels")
        return featured
        
    except Exception as e:
        logger.error(f"Error retrieving featured hostels: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve featured hostels"
        )


@router.get(
    "/nearby/{hostel_slug}",
    response_model=List[PublicHostelListItem],
    summary="Get nearby hostels",
    description="Find hostels near a specific hostel",
    responses={
        200: {"description": "Nearby hostels retrieved successfully"},
        404: {"description": "Reference hostel not found"},
    },
)
def get_nearby_hostels(
    hostel_slug: str = Path(
        ...,
        description="Slug of the reference hostel",
        example="grand-valley-hostel-mumbai"
    ),
    radius_km: float = Query(
        5.0,
        description="Search radius in kilometers",
        ge=0.5,
        le=50
    ),
    limit: int = Query(10, description="Maximum results", ge=1, le=50),
    service: HostelService = Depends(get_hostel_service),
) -> List[PublicHostelListItem]:
    """
    Find hostels near a reference hostel.
    
    Useful for showing alternatives or similar options.
    
    Args:
        hostel_slug: Reference hostel slug
        radius_km: Search radius in kilometers
        limit: Maximum number of results
        service: Hostel service instance
        
    Returns:
        List of nearby hostels
        
    Raises:
        HTTPException: If reference hostel not found
    """
    try:
        nearby = service.get_nearby(
            hostel_slug=hostel_slug,
            radius_km=radius_km,
            limit=limit
        )
        
        if nearby is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reference hostel not found"
            )
        
        logger.info(f"Found {len(nearby)} hostels near {hostel_slug}")
        return nearby
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding nearby hostels: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find nearby hostels"
        )


@router.get(
    "/cities/list",
    response_model=List[dict],
    summary="Get available cities",
    description="Get list of cities with available hostels",
    responses={
        200: {"description": "Cities list retrieved successfully"},
    },
)
def get_available_cities(
    service: HostelService = Depends(get_hostel_service),
) -> List[dict]:
    """
    Get list of cities with hostels.
    
    Returns cities along with hostel count.
    
    Args:
        service: Hostel service instance
        
    Returns:
        List of cities with counts
    """
    try:
        cities = service.get_available_cities()
        
        logger.info(f"Retrieved {len(cities)} cities with hostels")
        return cities
        
    except Exception as e:
        logger.error(f"Error retrieving cities: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cities"
        )